"""The diffuse sky and the clouds (P08.7): Erbs's split of the light into the
beam and the sky's, Kasten and Czeplak's dimming by clouds, the clouds'
QA override, and the sky's light inside past the roof's structure."""

import json
from datetime import UTC, datetime
from http import HTTPStatus

import numpy as np
import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services.scenarios import SceneChanges, changed
from greenhouse_sim.services.sunlight import plant_light
from greenhouse_sim.solar.glass import DIFFUSE_TRANSMITTANCE
from greenhouse_sim.solar.shadows import roof_shading
from greenhouse_sim.solar.sky import (
    CLEAR_CLEARNESS,
    DARK_CLEARNESS,
    cloud_factor,
    diffuse_share,
)
from greenhouse_sim.weather.sources import Clouded, ConstantWeather
from greenhouse_sim.world.site import DEFAULT_SITE

EQUINOX_NOON = datetime(2026, 3, 20, 11, 50, tzinfo=UTC)
# Solar noon in the solar lab's run, on the site's clock.
NOON_S = 12 * 3600 + 50 * 60
SEAM = 1e-9


def _light(weather: str) -> dict[str, float]:
    response = respond("GET", f"/api/scenarios/solar_lab/weather?t={NOON_S}&weather={weather}")
    assert response.status == HTTPStatus.OK
    light: dict[str, float] = json.loads(json.dumps(response.body))["light"]
    return light


def test_erbss_diffuse_share_is_continuous_and_falls_as_the_sky_clears() -> None:
    for seam in (DARK_CLEARNESS, CLEAR_CLEARNESS):
        assert diffuse_share(seam - SEAM) == pytest.approx(diffuse_share(seam + SEAM), abs=1e-3)
    clearness = np.linspace(0.0, 1.0, 101)
    shares = [diffuse_share(k) for k in clearness]
    # Erbs's polynomial dips a little below its floor just short of 0.8.
    assert all(later <= earlier + 1e-3 for earlier, later in zip(shares, shares[1:], strict=False))
    assert diffuse_share(0.0) == 1.0
    assert diffuse_share(0.9) == pytest.approx(0.165)


def test_clouds_dim_the_sky_to_a_quarter_when_full() -> None:
    factors = [cloud_factor(cover) for cover in (0.0, 25.0, 50.0, 75.0, 100.0)]

    assert factors[0] == 1.0
    assert factors[-1] == pytest.approx(0.25)
    assert factors == sorted(factors, reverse=True)
    # Half the sky clouded dims it by only 7%: thin cloud passes most light.
    assert cloud_factor(50.0) == pytest.approx(0.929, abs=0.001)


def test_the_light_falls_with_cloud_and_is_nearly_all_the_skys_under_full_cloud() -> None:
    lights = [_light(f"default@{cover}") for cover in (0, 25, 50, 75, 100)]
    totals = [light["ghi_w_m2"] for light in lights]

    assert totals == sorted(totals, reverse=True)
    # A clear equinox noon: a fifth of the light the sky's; under full cloud
    # nearly all of it.
    assert lights[0]["dhi_w_m2"] / lights[0]["ghi_w_m2"] == pytest.approx(0.21, abs=0.03)
    assert lights[-1]["dhi_w_m2"] / lights[-1]["ghi_w_m2"] > 0.95
    assert totals[-1] == pytest.approx(0.25 * totals[0])


def test_the_clouds_override_dims_any_weather_from_its_own_sky() -> None:
    # The cold spring day's own sky is half clouded.
    own = _light("cold_spring_day")["ghi_w_m2"]
    darker = _light("cold_spring_day@80")["ghi_w_m2"]
    assert darker == pytest.approx(own * cloud_factor(80.0) / cloud_factor(50.0))
    # Constant weather's radiation, measured under its own clear sky.
    constant = Clouded(ConstantWeather(global_radiation_w_m2=400.0).source(DEFAULT_SITE), 100.0)
    clouded = constant.at(EQUINOX_NOON)
    assert clouded.global_radiation_w_m2 == pytest.approx(100.0)
    assert clouded.cloud_cover_pct == 100.0
    # And the scenario keeps the override.
    config = changed(SCENARIO_REGISTRY["solar_lab"], SceneChanges(weather="default@80"))
    assert config.cloud_cover_pct == 80.0
    assert config.run_weather().at(0.0).cloud_cover_pct == 80.0


@pytest.mark.parametrize("weather", ["default@120", "default@-5", "default@cloudy"])
def test_a_cloud_cover_beyond_the_sky_is_refused(weather: str) -> None:
    response = respond("GET", f"/api/scenarios/solar_lab/weather?weather={weather}")

    assert response.status == HTTPStatus.BAD_REQUEST
    assert "a cloud cover runs from 0 to 100 %" in json.dumps(response.body)


def test_the_roofs_structure_covers_a_twentieth_of_the_climate_boxs_plan() -> None:
    # Four frames of two rafters, each 6 cm wide over its 3.2 m run, and the
    # two eave gutters' inner halves, 10 cm along the 12 m house, over its
    # 12 m by 6.4 m.
    expected = (4 * 2 * 0.06 * 3.2 + 2 * 0.1 * 12.0) / (12.0 * 6.4)

    assert roof_shading(SCENARIO_REGISTRY["climate_box"].envelope) == pytest.approx(expected)
    light = plant_light("solar_lab", "default", "default")
    assert light.sunlight.diffuse_passed == pytest.approx(DIFFUSE_TRANSMITTANCE * (1 - expected))


def test_clouds_soften_the_shadows() -> None:
    # The plants behind the crates against those in the open, at noon.
    def contrast(weather: str) -> float:
        par = plant_light("solar_lab", "default", weather).par_at(NOON_S)
        return par["solar_lab_plant_002"] / par["solar_lab_plant_016"]

    clear, cloudy, overcast = contrast("default"), contrast("default@80"), contrast("default@100")
    assert clear < 0.25 < cloudy < overcast
    assert overcast > 0.9
