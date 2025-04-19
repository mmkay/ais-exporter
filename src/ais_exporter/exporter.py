"""
This script collects data from a ais service and exposes them to the
Prometheus.io monitoring server for aggregation and later visualisation.
"""

import asyncio
import datetime
import json
import logging
import math
from math import asin, atan, cos, degrees, radians, sin, sqrt
from typing import Any, Dict, NamedTuple, Optional, Sequence, Tuple

import aiohttp
from aioprometheus import Gauge
from aioprometheus.service import Service

from .metrics import Specs

PositionType = Tuple[float, float]
MetricSpecItemType = Tuple[str, str, str]
MetricsSpecGroupType = Sequence[MetricSpecItemType]

logger = logging.getLogger(__name__)

shipsKeys = (
    "altitude",
    "category",
    "flight",
    "hex",
    "lat",
    "lon",
    "messages",
    "mlat",
    "nucp",
    "rssi",
    "seen",
    "seen_pos",
    "speed",
    "squalk",
    "tisb",
    "track",
    "vert_rate",
    "rel_angle",
    "rel_direction",
)


# TODO add mapping of registration prefixes to country codes


class aisResources(NamedTuple):  # pylint: disable=missing-class-docstring
    base: str
    stats: str
    ships: str


class Position(NamedTuple):  # pylint: disable=missing-class-docstring
    latitude: float
    longitude: float


class KnowledgeBase(NamedTuple):  # pylint: disable=missing-class-docstring
    ships: Dict[str, dict]

def build_resources(base: str) -> aisResources:
    """Return a named tuple containing ais resource paths"""
    resources = aisResources(
        base=base,
        stats=f"{base}/stat.json",
        ships=f"{base}/ships_array.json",
    )
    return resources


def relative_angle(pos1: Position, pos2: Position) -> float:
    """
    Calculate the direction pos2 relative to pos1. Returns angle in degrees

    :param pos1: a Position tuple defining (lat, lon) of origin in decimal degrees
    :param pos2: a Position tuple defining (lat, lon) of target in decimal degrees

    :returns: angle in degrees
    :rtype: float
    """
    lat1, lon1, lat2, lon2 = [
        x for x in (*pos1, *pos2)  # pylint: disable=unnecessary-comprehension
    ]

    # Special case - same lat as origin: 90 degrees or 270 degrees
    #
    #    |
    # -x-o-x-
    #    |

    if lat2 == lat1:
        if lon2 > lon1:
            return 90
        else:
            return 270

    deg = degrees(atan((lon2 - lon1) / (lat2 - lat1)))

    # Sign of results from the calculation above
    #
    #  - | +  (lat2>lat1)
    # ---o---
    #  + | -  (lat2<lat1)
    #
    # conversion needed to express in terms of 360 degrees

    if lat2 > lat1:
        return (360 + deg) % 360
    else:
        return 180 + deg


# lookup table for directions - each step is 22.5 degrees
direction_lut = (
    "N",
    "NE",
    "NE",
    "E",
    "E",
    "SE",
    "SE",
    "S",
    "S",
    "SW",
    "SW",
    "W",
    "W",
    "NW",
    "NW",
    "N",
)


def relative_direction(angle: float) -> str:
    """
    Convert relative angle in degrees into direction (N/NE/E/SE/S/SW/W/NW)
    """
    return direction_lut[int(angle / 22.5)]


def haversine_distance(
        pos1: Position, pos2: Position, radius: float = 6371.0e3
) -> float:
    """
    Calculate the distance between two points on a sphere (e.g. Earth).
    If no radius is provided then the default Earth radius, in meters, is
    used.

    The haversine formula provides great-circle distances between two points
    on a sphere from their latitudes and longitudes using the law of
    haversines, relating the sides and angles of spherical triangles.

    `Reference <https://en.wikipedia.org/wiki/Haversine_formula>`_

    :param pos1: a Position tuple defining (lat, lon) in decimal degrees
    :param pos2: a Position tuple defining (lat, lon) in decimal degrees
    :param radius: radius of sphere in meters.

    :returns: distance between two points in meters.
    :rtype: float
    """
    lat1, lon1, lat2, lon2 = [radians(x) for x in (*pos1, *pos2)]

    hav = (
            sin((lat2 - lat1) / 2.0) ** 2
            + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2.0) ** 2
    )
    distance = 2 * radius * asin(sqrt(hav))
    return distance


def create_gauge_metric(label: str, doc: str, prefix: str = "") -> Gauge:
    """Create a Gauge metric

    :param label: A label for the metric.

    :param doc: A help string for the metric.

    :param prefix: An optional prefix for the metric label that applies a
        common start string to the metric which simplifies locating the
        metrics in Prometheus because they will all be grouped together when
        searching.
    """
    gauge = Gauge(f"{prefix}{label}", doc)
    return gauge


async def _fetch(
        resource: str,
        timeout: float = 2.0
) -> Dict[Any, Any]:
    """Fetch JSON data from a web or file resource and return a dict"""
    logger.debug(f"fetching {resource}")
    if resource.startswith("http"):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        resource, timeout=timeout
                ) as resp:
                    if not resp.status == 200:
                        raise Exception(f"Fetch failed {resp.status}: {resource}")
                    data = await resp.json()
        except asyncio.TimeoutError:
            raise Exception(f"Request timed out to {resource}") from None
        except aiohttp.ClientError as exc:
            raise Exception(f"Client error {exc}, {resource}") from None
    else:
        with open(resource, "rt") as fd:  # pylint: disable=unspecified-encoding
            data = json.loads(fd.read())

    return data


class ais_exporter:
    """
    This class is responsible for fetching, parsing and exporting ais
    metrics to Prometheus.
    """

    def __init__(
            self,
            resource_path: str,
            host: str = "",
            port: int = 9205,
            ships_interval: int = 10,
            stats_interval: int = 60,
            time_periods: Sequence[str] = ("last1min",),
            origin: PositionType = None,
            fetch_timeout: float = 2.0,
    ) -> None:
        """
        :param resource_path: The base ais resource address. This can be
          a web address or a directory path.
        :param host: The host to expose Prometheus metrics on. Defaults
          to listen on all interfaces.
        :param port: The port to expose Prometheus metrics on. Defaults to
          port 9205.
        :param ships_interval: number of seconds between processing the
          ais ships data. Defaults to 10 seconds.
        :param stats_interval: number of seconds between processing the
          ais stats data. Defaults to 60 seconds as the data only
          seems to be updated at 60 second intervals.
        :param time_periods: A list of time period keys to extract from the
          statistics data. By default this is just the 'last1min' time
          period as Prometheus can provide the historical access.
        :param origin: a tuple of (lat, lon) representing the receiver
          location. The origin is used for distance calculations with
          ships data. If it is not provided then range calculations
          can not be performed and the maximum range metric will always
          be zero.
        :param fetch_timeout: The number of seconds to wait for a response
          from ais.
        """
        self.resources = build_resources(resource_path)
        self.loop = asyncio.get_event_loop()
        self.host = host
        self.port = port
        self.prefix = "ais_"
        self.ships_interval = datetime.timedelta(seconds=ships_interval)
        self.stats_interval = datetime.timedelta(seconds=stats_interval)
        self.stats_time_periods = time_periods
        self.origin = Position(*origin) if origin else None
        self.fetch_timeout = fetch_timeout
        self.svr = Service()
        self.stats_task = None  # type: Optional[asyncio.Task]
        self.ships_task = None  # type: Optional[asyncio.Task]
        self.knowledge_base = None
        self.initialise_metrics()
        logger.info(f"Monitoring ais resources at: {self.resources.base}")
        logger.info(
            f"Refresh rates: ships={self.ships_interval}, statstics={self.stats_interval}"
        )
        logger.info(f"Origin: {self.origin}")

    async def start(self) -> None:
        """Start the monitor"""
        await self.svr.start(addr=self.host, port=self.port)
        logger.info(f"serving ais prometheus metrics on: {self.svr.metrics_url}")

        # fmt: off
        self.stats_task = asyncio.ensure_future(self.updater_stats())  # type: ignore
        self.ships_task = asyncio.ensure_future(self.updater_ships())  # type: ignore
        # fmt: on

    async def stop(self) -> None:
        """Stop the monitor"""

        if self.stats_task:
            self.stats_task.cancel()
            try:
                await self.stats_task
            except asyncio.CancelledError:
                pass
            self.stats_task = None

        if self.ships_task:
            self.ships_task.cancel()
            try:
                await self.ships_task
            except asyncio.CancelledError:
                pass
            self.ships_task = None

        await self.svr.stop()

    def initialise_metrics(self) -> None:
        """Create metrics

        This method initialises a dict as the metrics attribute.

        The metrics dict has two str keys; one is `ships` and the other
        is `stats`.
        The `ships` key stores ships summary metrics using a value
        of Dict[str, Gauge].

        The `stats` key stores metrics under group keys. It has a value
        of Dict[str, Dict[str, Gauge]]
        """
        self.metrics = {"ships": {}}  # type: ignore

        # ships
        d = self.metrics["ships"]
        for (name, label, doc) in Specs["ships"]:  # type: ignore
            d[name] = create_gauge_metric(label, doc, prefix=self.prefix)

        # # statistics
        # for group, metrics_specs in Specs["stats"].items():  # type: ignore
        #     d = self.metrics["stats"].setdefault(group, {})
        #     for name, label, doc in metrics_specs:
        #         d[name] = create_gauge_metric(label, doc, prefix=self.prefix)


    async def updater_stats(self) -> None:
        """
        This long running coroutine task is responsible for fetching current
        statistics from ais and then updating internal metrics.
        """
        while True:
            start = datetime.datetime.now()
            try:
                stats = await _fetch(self.resources.stats)
                self.process_stats(stats, time_periods=self.stats_time_periods)
            except Exception as exc:  # pylint: disable=broad-except
                logger.error(f"Error fetching ais stats data: {exc}")

            # wait until next collection time
            end = datetime.datetime.now()
            wait_seconds = (start + self.stats_interval - end).total_seconds()
            await asyncio.sleep(wait_seconds)

    async def updater_ships(self) -> None:
        """
        This long running coroutine task is responsible for fetching current
        statistics from ais and then updating internal metrics.
        """
        while True:
            start = datetime.datetime.now()
            try:
                ships = await _fetch(self.resources.ships)
                self.process_ships(ships)
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception(f"Error fetching ais ships data")

            # wait until next collection time
            end = datetime.datetime.now()
            wait_seconds = (start + self.ships_interval - end).total_seconds()
            await asyncio.sleep(wait_seconds)

    def process_stats(
            self, stats: dict, time_periods: Sequence[str] = ("last1min",)
    ) -> None:
        """Process ais statistics into exported metrics.

        :param stats: a dict containing ais statistics data.
        """
        # TODO add stats parsing for AIS-catcher
        # metrics = self.metrics["stats"]  # type: Dict[str, Dict[str, Gauge]]
        #
        # for time_period in time_periods:
        #     try:
        #         tp_stats = stats[time_period]
        #     except KeyError:
        #         logger.exception(f"Problem extracting time period: {time_period}")
        #         continue
        #
        #     labels = dict(time_period=time_period)
        #
        #     for key, gauge in metrics.items():
        #         d = tp_stats[key] if key else tp_stats
        #         for name, metric in gauge.items():
        #             try:
        #                 value = d[name]
        #                 # 'accepted' values are in a list
        #                 if isinstance(value, list):
        #                     value = value[0]
        #             except KeyError:
        #                 # 'signal' and 'peak_signal' are not present if
        #                 # there are no ships.
        #                 if name not in ["peak_signal", "signal"]:
        #                     key_str = f" {key} " if key else " "
        #                     logger.warning(
        #                         f"Problem extracting{key_str}item '{name}' from: {d}"
        #                     )
        #                 value = math.nan
        #             metric.set(labels, value)

    def process_ships(self, ships: dict, threshold: int = 15) -> None:
        """Process ships statistics into exported metrics.

        :param ships: a dict containing ships data.
        :param threshold: only let ships seen within this threshold to
          contribute to the metrics.
        """


        d = self.metrics["ships"]
        for a in ships["values"]:
            ship_data = {
                "mmsi": a[0],
                "name": a[31],
                "country": a[22],
            }
            d["lat"].set(ship_data, a[1])
            d["lon"].set(ship_data, a[2])


        logger.debug(
            f"ships: observed={len(ships)}, "
        )
