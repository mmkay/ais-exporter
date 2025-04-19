# AIS Exporter

AIS exporter uses data from AIS-catcher in order to expose metrics on ships. It's based on 
[claws' dump1090exporter](https://github.com/claws/dump1090-exporter) with changes from my own fork.

## Install

The ais exporter is implemented as a Python3.6+ package that can be
installed using the Python package manager *pip*. It is recommended to install
this package into a virtual environment.

```shell
$ pip install ais-exporter
```

The package can optionally make use of the *uvloop* package which provides a
more efficient implementation of the asyncio event loop.

```shell
$ pip install ais-exporter[uvloop]
```

The ais-exporter has also been packaged into a Docker container. See the
[Docker](#docker) section below for more details about that.

## Run

The ais exporter can be run from the command line using the console entry
point script configured as part of the installation.

The ais exporter accepts a number of command line arguments which can be
displayed using the standard command line help request.

```shell
$ ais-exporter -h
```

An example usage is shown below.

```shell
$ ais-exporter \
  --resource-path=http://192.168.1.201:8383 \
  --port=9205 \
  --latitude=-34.9285 \
  --longitude=138.6007 \
  --log-level info
```

The ``--resource-path`` argument defines the common base path to the various
ais resources used by the exporter. The resource path can be a URL or a
file system location.

In the example command the exporter is instructed to monitor a ais
instance running on a machine with the IP address 192.168.1.201 using the port
8080.

The ais-exporter can also monitor ais state via the file system if
you run it on the same machine as the ais process. In this scenario you
would pass a file system path to the ``--resource-path`` command line argument.

For example:

```shell
$ ais-exporter \
  --resource-path=/path/to/ais-base-dir/data \
  ...
```

A more concrete example for ais-fa would be:

```shell
$ ais-exporter \
  --resource-path=/run/ais-fa/ \
  ...
```

The exporter uses the ``resources-path`` value to construct the following
resources:

  - {resource-path}/receiver.json
  - {resource-path}/ships.json
  - {resource-path}/stats.json

Receiver data is read from ``{resource-path}/receiver.json`` every 10 seconds
until a location can be obtained. Once a location has been read from the
resource then it is only polled every 300 seconds. However, in most cases the
ais tool is not configured with the receivers position.

ships data is read from ``{resource-path}/ships.json`` every 10 seconds.
This can be modified by specifying a new value with the ``--ships-interval``
argument.

Statistics data is read from ``{resource-path}/stats.json`` every 60 seconds,
as the primary metrics being exported are extracted from the *last1min* time
period. This too can be modified by specifying an alternative value with the
``--stats-interval`` argument.

The example command uses the ``--port`` argument to instruct the exporter to
exposes a metrics service on port 9205. This is where Prometheus would scrape
the metrics from. By default the port is configured to use 9205 so it only
needs to be specified if you want to change the port to a different value.

The example command uses the ``--latitude`` and ``--longitude`` arguments
to instruct the exporter to use a specific receiver origin (lat, lon). By
providing the exporter with the receiver's location it can calculate ranges
to ships. Note that if the receiver position is set within the ais
tool (and accessible from the ``{resource-path}/receivers.json`` resource)
then the exporter will use that data as the origin.

The metrics that the ais exporter provides to Prometheus can be
accessed for debug and viewing using curl or a browser by fetching from
the metrics route url. For example:

```shell
$ curl -s http://0.0.0.0:9205/metrics | grep -v "#"
ais_ships_recent_max_range{time_period="latest"} 1959.0337385807418
ais_messages_total{time_period="latest"} 90741
ais_recent_ships_observed{time_period="latest"} 4
ais_recent_ships_with_multilateration{time_period="latest"} 0
ais_recent_ships_with_position{time_period="latest"} 1
ais_stats_cpr_airborne{time_period="last1min"} 176
ais_stats_cpr_airborne{time_period="total"} 18293
...
```

The metrics exposed by the ais-exporter are all prefixed with the
*ais_* string so as to provide a helpful namespacing which makes them
easier to find in visualisation tools such as Grafana.

The exporter exposes generalised metrics for statistics and uses the multi
dimensional label capability of Prometheus metrics to include information
about which group the metric is part of.

To extract information for the peak signal metric that ais aggregated
over the last 1 minute you would specify the ``time_period`` for that group:

```shell
ais_stats_local_peak_signal{job="ais", time_period="last1min"}
```

In the ``stats.json`` data there are 5 top level keys that contain statistics
for a different time period, defined by the "start" and "end" subkeys. The top
level keys are:

- *latest* which covers the time between the end of the "last1min" period and
  the current time. In my ais setup this is always empty.
- *last1min* which covers a recent 1-minute period. This may be up to 1 minute
  out of date (i.e. "end" may be up to 1 minute old)
- *last5min* which covers a recent 5-minute period. As above, this may be up
  to 1 minute out of date.
- *last15min* which covers a recent 15-minute period. As above, this may be up
  to 1 minute out of date.
- *total* which covers the entire period from when ais was started up to
  the current time.

By default only the *last1min* time period is exported as Prometheus can be
used for accessing historical data.


## Prometheus Configuration

Prometheus needs to be told where to fetch the ais metrics from. The
Prometheus configuration file should be updated with a new entry under the
'scrape_configs' block, that looks something like this:

```yaml
scrape_configs:
  - job_name: 'ais'
    scrape_interval: 10s
    scrape_timeout: 5s
    static_configs:
      - targets: ['192.168.1.201:9205']
```

## Visualisation

The Grafana visualisation tool can display nice looking charts and it
supports Prometheus.

## Docker

The ais exporter has been packaged into a Docker container on DockerHub.
This can simplify running it in some environments. The container is configured
with an entry point that runs the ais exporter application. The default
command argument is ``--help`` which will display help information.

```shell
$ docker run -it --rm clawsicus/ais-exporter
usage: ais-exporter [-h] [--resource-path <ais url>]
...
```

To run the ais exporter container in your environment simply pass your
own custom command line arguments to it:

```shell
$ docker run -p 9205:9205 \
  --detach \
  clawsicus/ais-exporter \
  --resource-path=http://192.168.1.201:8383 \
  --latitude=-34.9285 \
  --longitude=138.6007
```

You can then check the metrics being exposed to Prometheus by fetching them
using curl.

```shell
$ curl http://127.0.0.1:9205/metrics
```

Next you would configure a Prometheus server to scape the ais-exporter
container on port 9205.


## Demonstration

A demonstration environment can be found in the ``demo`` directory. It uses
Docker Compose to orchestrate containers running ais-exporter, Prometheus
and Grafana to facilitate experimentation with metric collection and graphing.

This provides a really quick and easy method for checking out the
ais-exporter.


## Developer Notes

### Python Release Process

The following steps are used to make a new software release:

- Ensure current branch is set to master and is up to date.

- Create a virtual environment, install dependencies and the ais-exporter.

  ```shell
  $ make venv
  $ source venv/bin/activate
  (d1090exp) $
  ```

- Ensure all checks are passing.

  ```shell
  (d1090exp) $ make checks
  ```

- Ensure that the version label in ``__init__.py`` has been updated.

- Create the distribution. This project produces an artefact called a pure
  Python wheel. Only Python3 is supported by this package.

  ```shell
  (d1090exp) $ make dist
  ```

- Upload the new release to PyPI.

  ```shell
  (d1090exp) $ make dist-upload
  ```

- Create and push a repo tag to Github.

  ```shell
  $ git tag YY.MM.MICRO -m "A meaningful release tag comment"
  $ git tag  # check release tag is in list
  $ git push --tags origin master
  ```

  - Github will create a release tarball at:

    https://github.com/{username}/{repo}/tarball/{tag}.tar.gz


### Docker Release Process

The following steps are used to make a new software release:

- Generate the ais-exporter Python package distribution.

  ```shell
  (d1090exp) $ make dist
  ```

- Log in to the Docker user account which will hold the public image.

  ```shell
  (d1090exp) $ docker login
  username
  password
  ```

- Build the ais-exporter Docker container.

  ```shell
  (d1090exp) $ docker build -t clawsicus/ais-exporter .
  ```

- Perform a simple test of the container by specifying its full namespace to
  run that container image.

  ```shell
  $ docker run -it --rm clawsicus/ais-exporter
  usage: ais-exporter [-h] [--resource-path <ais url>]
  ...
  ```

- Test the container by configuring it to connect to a ais service.

  ```shell
  $ docker run -p 9205:9205 \
    --detach \
    clawsicus/ais-exporter \
    --resource-path=http://192.168.1.201:8383 \
    --latitude=-34.9285 \
    --longitude=138.6007
  ```

  Confirm that metrics are being collected and exposed by checking metrics
  are being exposed to Prometheus by fetching them using curl.

  ```shell
  $ curl http://127.0.0.1:9205/metrics
  ```

- Publish the new container to DockerHub using:

  ```shell
  (d1090exp) $ docker push clawsicus/ais-exporter:<version>
  ```
