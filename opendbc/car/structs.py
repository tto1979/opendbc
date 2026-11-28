import os
from dataclasses import dataclass

import capnp
from opendbc.car.common.basedir import BASEDIR

capnp.remove_import_hook()
car = capnp.load(os.path.join(BASEDIR, "car.capnp"), imports=[BASEDIR])

CarState = car.CarState
RadarData = car.RadarData
CarControl = car.CarControl
CarParams = car.CarParams

CarStateT = capnp.lib.capnp._StructModule
RadarDataT = capnp.lib.capnp._StructModule
CarControlT = capnp.lib.capnp._StructModule
CarParamsT = capnp.lib.capnp._StructModule


class TopFlags:
  LateralALKA = 1
  NNFF = 2
  ToyotaStockLong = 2 ** 2
  ToyotaTSSPTune = 2 ** 3
  ToyotaAutoLock = 2 ** 4
  ToyotaAutoUnlock = 2 ** 5
  ToyotaReverseAccChange = 2 ** 6
  ToyotaTSSPSNG = 2 ** 7
  ToyotaBSM = 2 ** 8
  ToyotaAutoBrakeHold = 2 ** 9
  ToyotaExperimentalMode = 2 ** 10
  ToyotaDriveMode = 2 ** 11


# TOP-only state and params, kept out of car.capnp so its ordinals stay in sync with upstream.
# openpilot publishes these as custom.CarStateTOP / custom.CarParamsTOP; field names must match.
@dataclass
class CarStateTOP:
  brakeholdGovernor: bool = False
  accelProfile: int = 0


@dataclass
class CarParamsTOP:
  experimentalModeViaWheel: bool = True
  twilsoncoNNFF: bool = False
  nnModelName: str = ""
  nnModelFuzzyMatch: bool = False
  # longitudinal stopping/starting tune, dropped from upstream CarParams in 0.11.2 (defaults = upstream's old defaults)
  vEgoStopping: float = 0.5  # [m/s] speed at which the car goes into stopping state
  vEgoStarting: float = 0.5  # [m/s] speed at which the car goes into starting state
  stoppingDecelRate: float = 0.8  # [m/s^2/s] while trying to stop
