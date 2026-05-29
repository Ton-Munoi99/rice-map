[Open-Meteo](https://open-meteo.com/)

* * *

[Home](https://open-meteo.com/) [Features](https://open-meteo.com/en/features) [Pricing](https://open-meteo.com/en/pricing) [API Docs](https://open-meteo.com/en/docs)

* * *

[GitHub](https://github.com/open-meteo/open-meteo) [X](https://x.com/open_meteo)

Toggle theme

# Weather Forecast API

Seamless integration of high-resolution weather models with up 16 days forecast

**Weather Forecast**

- [Weather Forecast](https://open-meteo.com/en/docs)
  - [DWD Germany](https://open-meteo.com/en/docs/dwd-api)
  - [NOAA U.S.](https://open-meteo.com/en/docs/gfs-api)
  - [Météo-France](https://open-meteo.com/en/docs/meteofrance-api)
  - [ECMWF](https://open-meteo.com/en/docs/ecmwf-api)
  - [UK Met Office](https://open-meteo.com/en/docs/ukmo-api)
  - [KMA Korea](https://open-meteo.com/en/docs/kma-api)
  - [JMA Japan](https://open-meteo.com/en/docs/jma-api)
  - [MeteoSwiss](https://open-meteo.com/en/docs/meteoswiss-api)
  - [MET Norway](https://open-meteo.com/en/docs/metno-api)
  - [GEM Canada](https://open-meteo.com/en/docs/gem-api)
  - [BOM Australia](https://open-meteo.com/en/docs/bom-api)
  - [CMA China](https://open-meteo.com/en/docs/cma-api)
  - [KNMI Netherlands](https://open-meteo.com/en/docs/knmi-api)
  - [DMI Denmark](https://open-meteo.com/en/docs/dmi-api)
  - [ItaliaMeteo](https://open-meteo.com/en/docs/italia-meteo-arpae-api)
  - [GeoSphere Austria](https://open-meteo.com/en/docs/geosphere-austria-api)
- [Historical Weather](https://open-meteo.com/en/docs/historical-weather-api)
  - [Historical Forecast](https://open-meteo.com/en/docs/historical-forecast-api)
  - [Single Runs](https://open-meteo.com/en/docs/single-runs-api)
  - [Previous Model Runs](https://open-meteo.com/en/docs/previous-runs-api)
- [Ensemble Models](https://open-meteo.com/en/docs/ensemble-api)
  - [Ensemble Mean API](https://open-meteo.com/en/docs/ensemble-mean-api)
- [Seasonal Forecast](https://open-meteo.com/en/docs/seasonal-forecast-api)
- [Climate Change](https://open-meteo.com/en/docs/climate-api)
- [Marine Forecast](https://open-meteo.com/en/docs/marine-weather-api)
- [Air Quality](https://open-meteo.com/en/docs/air-quality-api)
- [Satellite Radiation](https://open-meteo.com/en/docs/satellite-radiation-api)
- [Geocoding](https://open-meteo.com/en/docs/geocoding-api)
- [Elevation](https://open-meteo.com/en/docs/elevation-api)
- [Flood](https://open-meteo.com/en/docs/flood-api)

[**Location and Time**](https://open-meteo.com/en/docs#location_and_time)

Location:

CoordinatesListBounding box

Latitude

Longitude

Not set (GMT+0)Timezone

Search

Time:

Forecast LengthTime Interval

7 days (default)Forecast days

0 days (default)Past days

By default, we provide forecasts for 7 days, but you can access forecasts for up to 16
days. If you're interested in past weather data, you can use the Past Days feature to access archived forecasts.

[**Hourly Weather Variables**](https://open-meteo.com/en/docs#hourly_weather_variables)

Temperature (2 m)

Relative Humidity (2 m)

Dewpoint (2 m)

Apparent Temperature

Precipitation Probability

Precipitation (rain + showers + snow)

Rain

Showers

Snowfall

Snow Depth

Weather code

Sea Level Pressure

Surface Pressure

Cloud Cover Total

Cloud Cover Low

Cloud Cover Mid

Cloud Cover High

Visibility

Evapotranspiration

Reference Evapotranspiration (ET₀)

Vapour Pressure Deficit

Wind Speed (10 m)

Wind Speed (80 m)

Wind Speed (120 m)

Wind Speed (180 m)

Wind Direction (10 m)

Wind Direction (80 m)

Wind Direction (120 m)

Wind Direction (180 m)

Wind Gusts (10 m)

Temperature (80 m)

Temperature (120 m)

Temperature (180 m)

Soil Temperature (0 cm)

Soil Temperature (6 cm)

Soil Temperature (18 cm)

Soil Temperature (54 cm)

Soil Moisture (0-1 cm)

Soil Moisture (1-3 cm)

Soil Moisture (3-9 cm)

Soil Moisture (9-27 cm)

Soil Moisture (27-81 cm)

## Additional Variables And Options

UV Index

UV Index Clear Sky

Is Day or Night

Sunshine Duration

Wet Bulb Temperature (2 m)

Total Column Integrated Water Vapour

CAPE

Lifted Index

Convective Inhibition

Freezing Level Height

Boundary Layer Height PBL

Note: You can further adjust the forecast time range for hourly weather variables using &forecast\_hours= and &past\_hours= as shown below.

\- (default)Forecast Hours

\- (default)Past Hours

1 HourlyTemporal Resolution For Hourly Data

Terrain Optimised, Prefers LandGrid Cell Selection

## Solar Radiation Variables

Shortwave Solar Radiation GHI

Direct Solar Radiation

Diffuse Solar Radiation DHI

Direct Normal Irradiance DNI

Global Tilted Radiation GTI

Terrestrial Solar Radiation

Shortwave Solar Radiation GHI (Instant)

Direct Solar Radiation (Instant)

Diffuse Solar Radiation DHI (Instant)

Direct Normal Irradiance DNI (Instant)

Global Tilted Radiation GTI (Instant)

Terrestrial Solar Radiation (Instant)

Note: Solar radiation is averaged over the past hour. Use instant for radiation at the indicated time. For global tilted irradiance GTI please
specify Tilt and Azimuth below.

Panel Tilt (0° horizontal)

Panel Azimuth (0° S, -90° E, 90° W, ±180° N)

## Pressure Level Variables

Temperature

Relative Humidity

Cloud Cover

Wind Speed

Wind Direction

Geopotential Height

Temperature

1000 hPa (110 m)

975 hPa (320 m)

950 hPa (500 m)

925 hPa (800 m)

900 hPa (1000 m)

850 hPa (1500 m)

800 hPa (1900 m)

700 hPa (3 km)

600 hPa (4.2 km)

500 hPa (5.6 km)

400 hPa (7.2 km)

300 hPa (9.2 km)

250 hPa (10.4 km)

200 hPa (11.8 km)

150 hPa (13.5 km)

100 hPa (15.8 km)

70 hPa (17.7 km)

50 hPa (19.3 km)

30 hPa (22 km)

Note: Altitudes are approximate and in meters **above sea level** (not above ground). Use geopotential\_height to get precise altitudes above sea
level.

## Weather models

Best match

ECMWF IFS HRES 9km

ECMWF IFS 0.25°

ECMWF AIFS 0.25° Single

CMA GRAPES Global

BOM ACCESS Global

NCEP GFS Seamless

NCEP GFS Global 0.11°/0.25°

NCEP HRRR U.S. Conus

NCEP NBM U.S. Conus

NCEP NAM U.S. Conus

NCEP GFS GraphCast

NCEP AIGFS 0.25°

NCEP HGEFS 0.25° Ensemble Mean

JMA Seamless

JMA MSM

JMA GSM

KMA Seamless

KMA LDPS

KMA GDPS

DWD ICON Seamless

DWD ICON Global

DWD ICON EU

DWD ICON D2

GEM Seamless

GEM Global

GEM Regional

GEM HRDPS Continental

GEM HRDPS West

Météo-France Seamless

Météo-France ARPEGE World

Météo-France ARPEGE Europe

Météo-France AROME France

Météo-France AROME France HD

ItaliaMeteo ARPAE ICON 2I

MET Norway Nordic Seamless (with ECMWF)

MET Norway Nordic

KNMI Seamless (with ECMWF)

KNMI Harmonie AROME Europe

KNMI Harmonie AROME Netherlands

DMI Seamless (with ECMWF)

DMI Harmonie AROME Europe

UK Met Office Seamless

UK Met Office Global 10km

UK Met Office UK 2km

MeteoSwiss ICON Seamless

MeteoSwiss ICON CH1

MeteoSwiss ICON CH2

GeoSphere Seamless (with ECMWF)

GeoSphere AROME Austria

Note: The default Best Match provides the best forecast for any given
location worldwide. Seamless combines all models from a given provider into a
seamless prediction.

## 15-Minutely Weather Variables

Temperature (2 m)

Relative Humidity (2 m)

Dewpoint (2 m)

Apparent Temperature

Precipitation (rain + showers + snow)

Rain

Snowfall

Snowfall Height

Freezing Level Height

Sunshine Duration

Weather code

Wind Speed (10 m)

Wind Speed (80 m)

Wind Direction (10 m)

Wind Direction (80 m)

Wind Gusts (10 m)

Visibility

CAPE

Lightning Potential Index LPI

Is Day or Night

Shortwave Solar Radiation GHI

Direct Solar Radiation

Diffuse Solar Radiation DHI

Direct Normal Irradiance DNI

Global Tilted Radiation GTI

Terrestrial Solar Radiation

Shortwave Solar Radiation GHI (Instant)

Direct Solar Radiation (Instant)

Diffuse Solar Radiation DHI (Instant)

Direct Normal Irradiance DNI (Instant)

Global Tilted Radiation GTI (Instant)

Terrestrial Solar Radiation (Instant)

Note: Only available in Central Europe and North America. Other regions use
interpolated hourly data. Solar radiation is averaged over the 15 minutes. Use instant for radiation at the indicated time.

Note: You can further adjust the forecast time range for 15-minutely weather variables
using &forecast\_minutely\_15= and &past\_minutely\_15= as shown below.

\- (default)Forecast Minutely 15

\- (default)Past Minutely 15

[**Daily Weather Variables**](https://open-meteo.com/en/docs#daily_weather_variables)

Weather code

Maximum Temperature (2 m)

Minimum Temperature (2 m)

Maximum Apparent Temperature (2 m)

Minimum Apparent Temperature (2 m)

Sunrise

Sunset

Daylight Duration

Sunshine Duration

UV Index

UV Index Clear Sky

Rain Sum

Showers Sum

Snowfall Sum

Precipitation Sum

Precipitation Hours

Precipitation Probability Max

Maximum Wind Speed (10 m)

Maximum Wind Gusts (10 m)

Dominant Wind Direction (10 m)

Shortwave Radiation Sum

Reference Evapotranspiration (ET₀)

## Additional Daily Variables

Mean Temperature (2 m)

Mean Apparent Temperature (2 m)

Mean CAPE

Maximum CAPE

Minimum CAPE

Mean Cloud Cover

Maximum Cloud Cover

Minimum Cloud Cover

Mean Dewpoint (2 m)

Maximum Dewpoint (2 m)

Minimum Dewpoint (2 m)

Reference Evapotranspiration Sum (ET₀)

Growing Degree Days Base 0 Limit 50

Mean Leaf Wetness Probability

Mean Precipitation Probability

Minimum Precipitation Probability

Mean Relative Humidity (2 m)

Maximum Relative Humidity (2 m)

Minimum Relative Humidity (2 m)

Snowfall Water Equivalent Sum

Mean Sea Level Pressure

Maximum Sea Level Pressure

Minimum Sea Level Pressure

Mean Surface Pressure

Maximum Surface Pressure

Minimum Surface Pressure

Maximum Updraft

Mean Visibility

Minimum Visibility

Maximum Visibility

Mean Wind Gusts (10 m)

Mean Wind Speed (10 m)

Minimum Wind Gusts (10 m)

Minimum Wind Speed (10 m)

Mean Wet Bulb Temperature (2 m)

Maximum Wet Bulb Temperature (2 m)

Minimum Wet Bulb Temperature (2 m)

Maximum Vapour Pressure Deficit

[**Current Weather**](https://open-meteo.com/en/docs#current_weather)

Temperature (2 m)

Relative Humidity (2 m)

Apparent Temperature

Is Day or Night

Precipitation

Rain

Showers

Snowfall

Weather code

Cloud Cover Total

Sea Level Pressure

Surface Pressure

Wind Speed (10 m)

Wind Direction (10 m)

Wind Gusts (10 m)

Note: Current conditions are based on 15-minutely weather model data. Every weather variable
available in hourly data, is available as current condition as well.

[**Settings**](https://open-meteo.com/en/docs#settings)

Celsius °CTemperature Unit

km/hWind Speed Unit

MillimeterPrecipitation Unit

ISO 8601 (e.g. 2026-05-26)Timeformat

Usage licence:

Non-CommercialCommercialSelf-Hosted

Only for **non-commercial use** and less than 10.000 daily API calls. See [Terms](https://open-meteo.com/en/terms) for more details.

[**API Response**](https://open-meteo.com/en/docs#api_response)

Preview:

Chart & URLPythonTypeScriptSwiftOther

Loading...

Created with Highcharts 12.6.0°C52.52°N 13.42°E 38m above sea levelGenerated in 0.10ms, downloaded in 464ms, time in GMT+0temperature\_2m27 May08:0016:0028 May08:0016:0029 May08:0016:0030 May08:0016:0031 May08:0016:001 Jun08:0016:002 Jun08:0016:003 Jun1015202530Open-Meteo.com

[Download XLSX](https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&hourly=temperature_2m&format=xlsx) [Download CSV](https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&hourly=temperature_2m&format=csv)

API URL ( [Open in new tab](https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&hourly=temperature_2m) or copy this URL into your application)

[**Data Sources**](https://open-meteo.com/en/docs#data_sources)

Open-Meteo combines weather model output from multiple national weather services into a
continuous, seamlessly updated timeseries. Each time a model run is ingested, the forecast
data are stitched to the previous run without gaps or discontinuities, so the hourly
timeseries always reflects the latest available initialisation. For each location, the
highest-resolution applicable model is selected automatically.

Weather models cover different geographic areas at different resolutions and provide
different weather variables. Depending on the model, data have been interpolated to hourly
values or not all weather variables are available. Use the Weather models dropdown (just below the hourly variables) to select and compare individual models. To access
the full archive of past forecast runs as issued — useful for forecast verification or training
ML models — see the [Historical Forecast API](https://open-meteo.com/en/docs/historical-forecast-api) and the [Single Runs API](https://open-meteo.com/en/docs/single-runs-api).

| Weather Model | National Weather Provider | Origin Country | Resolution | Forecast Length | Update frequency |
| --- | --- | --- | --- | --- | --- |
| [ICON](https://open-meteo.com/en/docs/dwd-api) | Deutscher Wetterdienst (DWD) | Germany | 2 - 11 km | 7.5 days | Every 3 hours |
| [GFS & HRRR](https://open-meteo.com/en/docs/gfs-api) | NOAA | United States | 3 - 25 km | 16 days | Every hour |
| [ARPEGE & AROME](https://open-meteo.com/en/docs/meteofrance-api) | Météo-France | France | 1 - 25 km | 4 days | Every hour |
| [IFS & AIFS](https://open-meteo.com/en/docs/ecmwf-api) | ECMWF | European Union | 9 - 25km | 15 days | Every 6 hours |
| [UKMO](https://open-meteo.com/en/docs/ukmo-api) | UK Met Office | United Kingdom | 2 - 10 km | 7 days | Every hour |
| [KMA](https://open-meteo.com/en/docs/kma-api) | KMA Korea | Korea | 1.5 - 13 km | 12 days | Every 6 hours |
| [MSM & GSM](https://open-meteo.com/en/docs/jma-api) | JMA | Japan | 5 - 55 km | 11 days | Every 3 hours |
| [ICON CH](https://open-meteo.com/en/docs/meteoswiss-api) | MeteoSwiss | Switzerland | 1 - 2 km | 5 days | Every 3 hours |
| [MET Nordic](https://open-meteo.com/en/docs/metno-api) | MET Norway | Norway | 1 km | 2.5 days | Every hour |
| [GEM](https://open-meteo.com/en/docs/gem-api) | Canadian Weather Service | Canada | 2.5 km | 10 days | Every 6 hours |
| [ACCESS-G](https://open-meteo.com/en/docs/bom-api) | Australian Bureau of Meteorology (BOM) | Australia | 15 km | 10 days | Every 6 hours |
| [GFS GRAPES](https://open-meteo.com/en/docs/cma-api) | China Meteorological Administration (CMA) | China | 15 km | 10 days | Every 6 hours |
| [HARMONIE](https://open-meteo.com/en/docs/knmi-api) | KNMI | Netherlands | 2 km | 2.5 days | Every hour |
| [HARMONIE](https://open-meteo.com/en/docs/dmi-api) | DMI | Denmark | 2 km | 2.5 days | Every 3 hours |
| [ARPAE](https://open-meteo.com/en/docs/italia-meteo-arpae-api) | ItaliaMeteo | Italy | 2 km | 3 days | Every 12 hours |

You can find the update timings in the [model updates documentation](https://open-meteo.com/en/docs/model-updates).

[**API Documentation**](https://open-meteo.com/en/docs#api_documentation)

The API endpoint /v1/forecast accepts a geographical coordinate, a list of
weather variables and responds with a JSON hourly weather forecast for 7 days. Time always
starts at 0:00 today and contains 168 hours. If &forecast\_days=16 is set, up to 16 days of forecast can be returned. All URL parameters
are listed below:

| Parameter | Format | Required | Default | Description |
| --- | --- | --- | --- | --- |
| latitude, longitude | Floating point | Yes |  | Geographical WGS84 coordinates of the location. Multiple coordinates can be comma<br> separated. E.g. &latitude=52.52,48.85&longitude=13.41,2.35. To return<br> data for multiple locations the JSON output changes to a list of structures. CSV and<br> XLSX formats add a column location\_id. For North and South America<br> locations use negative longitudes, because they lie west of Greenwich. |
| elevation | Floating point | No |  | The elevation used for statistical downscaling. Per default, a [90 meter digital elevation model is used](https://openmeteo.substack.com/p/improving-weather-forecasts-with "Elevation based grid-cell selection explained"). You can manually set the elevation to correctly match mountain peaks. If &elevation=nan is specified, downscaling will be disabled and the API uses<br> the average grid-cell height. For multiple locations, elevation can also be comma separated. |
| hourly | String array | No |  | A list of weather variables which should be returned. Values can be comma separated,<br> or multiple &hourly= parameter in the URL can be used. |
| daily | String array | No |  | A list of daily weather variable aggregations which should be returned. Values can be<br> comma separated, or multiple &daily= parameter in the URL can be used. If<br> daily weather variables are specified, parameter timezone is required. |
| current | String array | No |  | A list of weather variables to get current conditions. |
| temperature\_unit | String | No | celsius | If fahrenheit is set, all temperature values are converted to Fahrenheit. |
| wind\_speed\_unit | String | No | kmh | Other wind speed speed units: ms, mph and kn |
| precipitation\_unit | String | No | mm | Other precipitation amount units: inch |
| timeformat | String | No | iso8601 | If format unixtime is selected, all time values are returned in UNIX<br> epoch time in seconds. Please note that all timestamp are in GMT+0! For daily values<br> with unix timestamps, please apply utc\_offset\_seconds again to get the correct date. |
| timezone | String | No | GMT | If timezone is set, all timestamps are returned as local-time and data<br> is returned starting at 00:00 local-time. Any time zone name from the [time zone database](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) is supported. If auto is set as a time zone, the coordinates will be automatically<br> resolved to the local time zone. For multiple coordinates, a comma separated list of timezones<br> can be specified. |
| past\_days | Integer (0-92) | No | 0 | If past\_days is set, yesterday or the day before yesterday data are also returned. |
| forecast\_days | Integer (0-16) | No | 7 | Per default, only 7 days are returned. Up to 16 days of forecast are possible. |
| forecast\_hours<br>forecast\_minutely\_15<br>past\_hours<br>past\_minutely\_15 | Integer (>0) | No |  | Similar to forecast\_days, the number of timesteps of hourly and 15-minutely data can<br> controlled. Instead of using the current day as a reference, the current hour or the<br> current 15-minute time-step is used. |
| start\_date<br>end\_date | String (yyyy-mm-dd) | No |  | The time interval to get weather data. A day must be specified as an ISO8601 date<br> (e.g. 2022-06-30). |
| start\_hour<br>end\_hour<br>start\_minutely\_15<br>end\_minutely\_15 | String (yyyy-mm-ddThh:mm) | No |  | The time interval to get weather data for hourly or 15 minutely data. Time must be<br> specified as an ISO8601 date (e.g. 2022-06-30T12:00). |
| models | String array | No | auto | Manually select one or more weather models. Per default, the best suitable weather<br> models will be combined. |
| cell\_selection | String | No | land | Set a preference how grid-cells are selected. The default land finds a<br> suitable grid-cell on land with [similar elevation to the requested coordinates using a 90-meter digital elevation\<br> model](https://openmeteo.substack.com/p/improving-weather-forecasts-with "Elevation based grid-cell selection explained"). sea prefers grid-cells on sea. nearest selects the nearest possible<br> grid-cell. |
| apikey | String | No |  | Only required to commercial use to access reserved API resources for customers. The<br> server URL requires the prefix customer-. See [pricing](https://open-meteo.com/en/pricing "Pricing information to use the weather API commercially") for more information. |

Additional optional URL parameters will be added. For API stability, no required parameters
will be added in the future!

[**Hourly Parameter Definition**](https://open-meteo.com/en/docs#hourly_parameter_definition)

The parameter &hourly= accepts the following values. Most weather variables are given
as an instantaneous value for the indicated hour. Some variables like precipitation are calculated
from the preceding hour as an average or sum.

| Variable | Valid time | Unit | Description |
| --- | --- | --- | --- |
| temperature\_2m | Instant | °C (°F) | Air temperature at 2 meters above ground |
| relative\_humidity\_2m | Instant | % | Relative humidity at 2 meters above ground |
| dew\_point\_2m | Instant | °C (°F) | Dew point temperature at 2 meters above ground |
| apparent\_temperature | Instant | °C (°F) | Apparent temperature is the perceived feels-like temperature combining wind chill<br> factor, relative humidity and solar radiation |
| pressure\_msl<br>surface\_pressure | Instant | hPa | Atmospheric air pressure reduced to mean sea level (msl) or pressure at surface.<br> Typically pressure on mean sea level is used in meteorology. Surface pressure gets<br> lower with increasing elevation. |
| cloud\_cover | Instant | % | Total cloud cover as an area fraction |
| cloud\_cover\_low | Instant | % | Low level clouds and fog up to 3 km altitude |
| cloud\_cover\_mid | Instant | % | Mid level clouds from 3 to 8 km altitude |
| cloud\_cover\_high | Instant | % | High level clouds from 8 km altitude |
| wind\_speed\_10m<br>wind\_speed\_80m<br>wind\_speed\_120m<br>wind\_speed\_180m | Instant | km/h (mph, m/s, knots) | Wind speed at 10, 80, 120 or 180 meters above ground. Wind speed on 10 meters is the<br> standard level. |
| wind\_direction\_10m<br>wind\_direction\_80m<br>wind\_direction\_120m<br>wind\_direction\_180m | Instant | ° | Wind direction at 10, 80, 120 or 180 meters above ground |
| wind\_gusts\_10m | Preceding hour max | km/h (mph, m/s, knots) | Gusts at 10 meters above ground as a maximum of the preceding hour |
| shortwave\_radiation | Preceding hour mean | W/m² | Shortwave solar radiation as average of the preceding hour. This is equal to the<br> total global horizontal irradiation |
| direct\_radiation<br>direct\_normal\_irradiance | Preceding hour mean | W/m² | Direct solar radiation as average of the preceding hour on the horizontal plane and<br> the normal plane (perpendicular to the sun) |
| diffuse\_radiation | Preceding hour mean | W/m² | Diffuse solar radiation as average of the preceding hour |
| global\_tilted\_irradiance | Preceding hour mean | W/m² | Total radiation received on a tilted pane as average of the preceding hour. The<br> calculation is assuming a fixed albedo of 20% and in isotropic sky. Please specify<br> tilt and azimuth parameter. Tilt ranges from 0° to 90° and is typically around 45°.<br> Azimuth should be close to 0° (0° south, -90° east, 90° west, ±180 north). If azimuth<br> is set to "nan", the calculation assumes a vertical tracker (east-west). If tilt is<br> set to "nan", it is assumed that the panel has a horizontal tracker (up-down). If both<br> are set to "nan", a bi-axial tracker is assumed. |
| vapour\_pressure\_deficit | Instant | kPa | Vapour Pressure Deficit (VPD) in kilopascal (kPa). For high VPD (>1.6), water<br> transpiration of plants increases. For low VPD (<0.4), transpiration decreases |
| cape | Instant | J/kg | Convective available potential energy. See [Wikipedia](https://en.wikipedia.org/wiki/Convective_available_potential_energy). |
| evapotranspiration | Preceding hour sum | mm (inch) | Evapotranspiration from land surface and plants that weather models assumes for this<br> location. Available soil water is considered. 1 mm evapotranspiration per hour equals<br> 1 liter of water per square meter. |
| et0\_fao\_evapotranspiration | Preceding hour sum | mm (inch) | ET₀ Reference Evapotranspiration of a well watered grass field. Based on [FAO-56 Penman-Monteith equations](https://www.fao.org/3/x0490e/x0490e04.htm) ET₀ is calculated from temperature, wind speed, humidity and solar radiation. Unlimited<br> soil water is assumed. ET₀ is commonly used to estimate the required irrigation for plants. |
| precipitation | Preceding hour sum | mm (inch) | Total precipitation (rain, showers, snow) sum of the preceding hour |
| snowfall | Preceding hour sum | cm (inch) | Snowfall amount of the preceding hour in centimeters. For the water equivalent in<br> millimeter, divide by 7. E.g. 7 cm snow = 10 mm precipitation water equivalent |
| precipitation\_probability | Preceding hour probability | % | Probability of precipitation with more than 0.1 mm of the preceding hour. Probability<br> is based on ensemble weather models with 0.25° (~27 km) resolution. 30 different<br> simulations are computed to better represent future weather conditions. |
| rain | Preceding hour sum | mm (inch) | Rain from large scale weather systems of the preceding hour in millimeter |
| showers | Preceding hour sum | mm (inch) | Showers from convective precipitation in millimeters from the preceding hour |
| weather\_code | Instant | WMO code | Weather condition as a numeric code. Follow WMO weather interpretation codes. See<br> table below for details. |
| snow\_depth | Instant | meters | Snow depth on the ground |
| freezing\_level\_height | Instant | meters | Altitude above sea level of the 0°C level |
| visibility | Instant | meters | Viewing distance in meters. Influenced by low clouds, humidity and aerosols. |
| soil\_temperature\_0cm<br>soil\_temperature\_6cm<br>soil\_temperature\_18cm<br>soil\_temperature\_54cm | Instant | °C (°F) | Temperature in the soil at 0, 6, 18 and 54 cm depths. 0 cm is the surface temperature<br> on land or water surface temperature on water. |
| soil\_moisture\_0\_to\_1cm<br>soil\_moisture\_1\_to\_3cm<br>soil\_moisture\_3\_to\_9cm<br>soil\_moisture\_9\_to\_27cm<br>soil\_moisture\_27\_to\_81cm | Instant | m³/m³ | Average soil water content as volumetric mixing ratio at 0-1, 1-3, 3-9, 9-27 and<br> 27-81 cm depths. |
| is\_day | Instant | Dimensionless | 1 if the current time step has daylight, 0 at night. |

[**15-Minutely Parameter Definition**](https://open-meteo.com/en/docs#15_minutely_parameter_definition)

The parameter &minutely\_15= can be used to get 15-minutely data. This data is based
on NOAA HRRR model for North America and DWD ICON-D2 and Météo-France AROME model for Central Europe.
If 15-minutely data is requested for other regions data is interpolated from 1-hourly to 15-minutely.

15-minutely data can be requested for other weather variables that are available for hourly
data, but will use interpolation.

| Variable | Valid time | Unit | HRRR | ICON-D2 | AROME |
| --- | --- | --- | --- | --- | --- |
| temperature\_2m | Instant | °C (°F) | x |  | x |
| relative\_humidity\_2m | Instant | % | x |  | x |
| dew\_point\_2m | Instant | °C (°F) | x |  | x |
| apparent\_temperature | Instant | °C (°F) | x |  | x |
| shortwave\_radiation | Preceding 15 minutes mean | W/m² | x | x |  |
| direct\_radiation<br>direct\_normal\_irradiance | Preceding 15 minutes mean | W/m² | x | x |  |
| global\_tilted\_irradiance<br>global\_tilted\_irradiance\_instant | Preceding 15 minutes mean | W/m² | x | x |  |
| diffuse\_radiation | Preceding 15 minutes mean | W/m² | x | x |  |
| sunshine\_duration | Preceding 15 minutes sum | seconds | x | x |  |
| lightning\_potential | Instant | J/kg |  | x |  |
| precipitation | Preceding 15 minutes sum | mm (inch) | x | x | x |
| snowfall | Preceding 15 minutes sum | cm (inch) | x | x | x |
| rain | Preceding 15 minutes sum | mm (inch) | x | x | x |
| showers | Preceding 15 minutes sum | mm (inch) |  | x |  |
| snowfall\_height | Instant | meters |  | x |  |
| freezing\_level\_height | Instant | meters |  | x |  |
| cape | Instant | J/kg | x | x | x |
| wind\_speed\_10m<br>wind\_speed\_80m | Instant | km/h (mph, m/s, knots) | x |  | x |
| wind\_direction\_10m<br>wind\_direction\_80m | Instant | ° | x |  | x |
| wind\_gusts\_10m | Preceding 15 min max | km/h (mph, m/s, knots) | x |  |  |
| visibility | Instant | meters | x |  | x |
| weather\_code | Instant | WMO code | x | x |  |

[**Pressure Level Variables**](https://open-meteo.com/en/docs#pressure_level_variables)

Pressure level variables do not have fixed altitudes. Altitude varies with atmospheric
pressure. 1000 hPa is roughly between 60 and 160 meters above sea level. Estimated altitudes
are given below. Altitudes are in meters above sea level (not above ground). For precise
altitudes, geopotential\_height can be used.

| Level (hPa) | 1000 | 975 | 950 | 925 | 900 | 850 | 800 | 700 | 600 | 500 | 400 | 300 | 250 | 200 | 150 | 100 | 70 | 50 | 30 |
| Altitude | 110 m | 320 m | 500 m | 800 m | 1000 m | 1500 m | 1900 m | 3 km | 4.2 km | 5.6 km | 7.2 km | 9.2 km | 10.4 km | 11.8 km | 13.5 km | 15.8 km | 17.7 km | 19.3 km | 22 km |

All pressure levels have valid times of the indicated hour (instant).

| Variable | Unit | Description |
| --- | --- | --- |
| temperature\_1000hPa<br>temperature\_975hPa, ... | °C (°F) | Air temperature at the specified pressure level. Air temperatures decrease linearly<br> with pressure. |
| relative\_humidity\_1000hPa<br>relative\_humidity\_975hPa, ... | % | Relative humidity at the specified pressure level. |
| dew\_point\_1000hPa<br>dew\_point\_975hPa, ... | °C (°F) | Dew point temperature at the specified pressure level. |
| cloud\_cover\_1000hPa<br>cloud\_cover\_975hPa, ... | % | Cloud cover at the specified pressure level. Cloud cover is approximated based on<br> relative humidity using [Sundqvist et al. (1989)](https://www.ecmwf.int/sites/default/files/elibrary/2005/16958-parametrization-cloud-cover.pdf). It may not match perfectly with low, mid and high cloud cover variables. |
| wind\_speed\_1000hPa<br>wind\_speed\_975hPa, ... | km/h (mph, m/s, knots) | Wind speed at the specified pressure level. |
| wind\_direction\_1000hPa<br>wind\_direction\_975hPa, ... | ° | Wind direction at the specified pressure level. |
| geopotential\_height\_1000hPa<br>geopotential\_height\_975hPa, ... | meter | Geopotential height at the specified pressure level. This can be used to get the<br> correct altitude in meter above sea level of each pressure level. Be careful not to<br> mistake it with altitude above ground. |

[**Daily Parameter Definition**](https://open-meteo.com/en/docs#daily_parameter_definition)

Aggregations are a simple 24 hour aggregation from hourly values. The parameter &daily= accepts the following values:

| Variable | Unit | Description |
| --- | --- | --- |
| temperature\_2m\_max<br>temperature\_2m\_mean<br>temperature\_2m\_min | °C (°F) | Maximum and minimum daily air temperature at 2 meters above ground |
| apparent\_temperature\_max<br>apparent\_temperature\_mean<br>apparent\_temperature\_min | °C (°F) | Maximum and minimum daily apparent temperature |
| precipitation\_sum | mm | Sum of daily precipitation (including rain, showers and snowfall) |
| rain\_sum | mm | Sum of daily rain |
| showers\_sum | mm | Sum of daily showers |
| snowfall\_sum | cm | Sum of daily snowfall |
| precipitation\_hours | hours | The number of hours with rain |
| precipitation\_probability\_max<br>precipitation\_probability\_mean<br>precipitation\_probability\_min | % | Probability of precipitation |
| weather\_code | WMO code | The most severe weather condition on a given day |
| sunrise<br>sunset | iso8601 | Sun rise and set times |
| sunshine\_duration | seconds | The number of seconds of sunshine per day is determined by calculating direct<br> normalized irradiance exceeding 120 W/m², following the WMO definition. Sunshine<br> duration will consistently be less than daylight duration due to dawn and dusk. |
| daylight\_duration | seconds | Number of seconds of daylight per day |
| wind\_speed\_10m\_max<br>wind\_gusts\_10m\_max | km/h (mph, m/s, knots) | Maximum wind speed and gusts on a day |
| wind\_direction\_10m\_dominant | ° | Dominant wind direction |
| shortwave\_radiation\_sum | MJ/m² | The sum of solar radiation on a given day in Megajoules |
| et0\_fao\_evapotranspiration | mm | Daily sum of ET₀ Reference Evapotranspiration of a well watered grass field |
| uv\_index\_max<br>uv\_index\_clear\_sky\_max | Index | Daily maximum in UV Index starting from 0. uv\_index\_clear\_sky\_max assumes cloud free conditions. Please follow the [official WMO guidelines](https://www.who.int/news-room/questions-and-answers/item/radiation-the-ultraviolet-(uv)-index) for ultraviolet index. |

[**JSON Return Object**](https://open-meteo.com/en/docs#json_return_object)

On success a JSON object will be returned.

```
{
    "latitude": 52.52,
    "longitude": 13.419,
    "elevation": 44.812,
    "generationtime_ms": 2.2119,
    "utc_offset_seconds": 0,
    "timezone": "Europe/Berlin",
    "timezone_abbreviation": "CEST",
    "hourly": {
        "time": ["2022-07-01T00:00", "2022-07-01T01:00", "2022-07-01T02:00", ...],
        "temperature_2m": [13, 12.7, 12.7, 12.5, 12.5, 12.8, 13, 12.9, 13.3, ...]
    },
    "hourly_units": {
        "temperature_2m": "°C"
    }
}
```

| Parameter | Format | Description |
| --- | --- | --- |
| latitude, longitude | Floating point | WGS84 of the center of the weather grid-cell which was used to generate this<br> forecast. This coordinate might be a few kilometres away from the requested<br> coordinate. |
| elevation | Floating point | The elevation from a 90 meter digital elevation model. This effects which grid-cell<br> is selected (see parameter cell\_selection). Statistical downscaling is<br> used to adapt weather conditions for this elevation. This elevation can also be<br> controlled with the query parameter elevation. If &elevation=nan is specified, all downscaling is disabled and the average grid-cell<br> elevation is used. |
| generationtime\_ms | Floating point | Generation time of the weather forecast in milliseconds. This is mainly used for<br> performance monitoring and improvements. |
| utc\_offset\_seconds | Integer | Applied timezone offset from the &timezone= parameter. |
| timezone<br>timezone\_abbreviation | String | Timezone identifier (e.g. Europe/Berlin) and abbreviation (e.g. CEST) |
| current | Object | For every chosen current weather variable, the data is provided as a numeric value.<br> In addition, time specifies the moment at which the data is valid. The interval represents the duration in seconds used for calculating backward-looking<br> sums or averages. For instance, an interval of 900 seconds (15 minutes) means that aggregated<br> metrics such as precipitation reflect the total from the previous 15 minutes. |
| hourly | Object | For each selected weather variable, data will be returned as a floating point array.<br> Additionally a time array will be returned with ISO8601 timestamps. |
| hourly\_units | Object | For each selected weather variable, the unit will be listed here. |
| daily | Object | For each selected daily weather variable, data will be returned as a floating point<br> array. Additionally a time array will be returned with ISO8601 timestamps. |
| daily\_units | Object | For each selected daily weather variable, the unit will be listed here. |

[**Errors**](https://open-meteo.com/en/docs#errors)

In case an error occurs, for example a URL parameter is not correctly specified, a JSON error
object is returned with a HTTP 400 status code.

```
{
    "error": true,
    "reason": "Cannot initialize WeatherVariable from invalid String value
	    tempeture_2m for key hourly"
}
```

[**Weather variable documentation**](https://open-meteo.com/en/docs#weather_variable_documentation)

### WMO Weather interpretation codes (WW)

| Code | Description |
| --- | --- |
| 0 | Clear sky |
| 1, 2, 3 | Mainly clear, partly cloudy, and overcast |
| 45, 48 | Fog and depositing rime fog |
| 51, 53, 55 | Drizzle: Light, moderate, and dense intensity |
| 56, 57 | Freezing Drizzle: Light and dense intensity |
| 61, 63, 65 | Rain: Slight, moderate and heavy intensity |
| 66, 67 | Freezing Rain: Light and heavy intensity |
| 71, 73, 75 | Snow fall: Slight, moderate, and heavy intensity |
| 77 | Snow grains |
| 80, 81, 82 | Rain showers: Slight, moderate, and violent |
| 85, 86 | Snow showers slight and heavy |
| 95 \* | Thunderstorm: Slight or moderate |
| 96, 99 \* | Thunderstorm with slight and heavy hail |

(\*) Thunderstorm forecast with hail is only available in Central Europe

[Open-Meteo](https://open-meteo.com/)

- [Features](https://open-meteo.com/en/features)
- [Pricing](https://open-meteo.com/en/pricing)
- [About us & Contact](https://open-meteo.com/en/about)
- [Licence](https://open-meteo.com/en/licence)
- [Terms & Privacy](https://open-meteo.com/en/terms)

[Weather APIs](https://open-meteo.com/en/docs)

- [Weather Forecast API](https://open-meteo.com/en/docs)
- [Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)
- [ECMWF API](https://open-meteo.com/en/docs/ecmwf-api)
- [GFS & HRRR Forecast API](https://open-meteo.com/en/docs/gfs-api)
- [Météo-France API](https://open-meteo.com/en/docs/meteofrance-api)
- [DWD ICON API](https://open-meteo.com/en/docs/dwd-api)
- [GEM API](https://open-meteo.com/en/docs/gem-api)
- [JMA API](https://open-meteo.com/en/docs/jma-api)
- [Met Norway API](https://open-meteo.com/en/docs/metno-api)

Other APIs

- [Ensemble API](https://open-meteo.com/en/docs/ensemble-api)
- [Climate Change API](https://open-meteo.com/en/docs/climate-api)
- [Marine Weather API](https://open-meteo.com/en/docs/marine-weather-api)
- [Air Quality API](https://open-meteo.com/en/docs/air-quality-api)
- [Geocoding API](https://open-meteo.com/en/docs/geocoding-api)
- [Elevation API](https://open-meteo.com/en/docs/elevation-api)
- [Flood API](https://open-meteo.com/en/docs/flood-api)

External

- [X](https://x.com/open_meteo)
- [Blog](https://openmeteo.substack.com/archive?sort=new)
- [GitHub](https://github.com/open-meteo/open-meteo)
- [Mastodon](https://fosstodon.org/@openmeteo)
- [Service status and uptime](https://status.open-meteo.com/)
- [Model Updates Overview](https://open-meteo.com/en/docs/model-updates)

© 2022-2026 Copyright: [Open-Meteo.com](https://open-meteo.com/)