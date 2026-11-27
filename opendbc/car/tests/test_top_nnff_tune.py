from opendbc.car import gen_empty_fingerprint, structs
from opendbc.car.car_helpers import interfaces
from opendbc.car.toyota.values import CAR as TOYOTA


def get_params(platform, car_fw, nnff):
  top_params = structs.TopFlags.NNFF if nnff else 0
  return interfaces[platform].get_params(platform, gen_empty_fingerprint(), car_fw, False, False, top_params, False)


class TestNNFFTorqueTune:
  def test_torque_cars_keep_their_tuning(self):
    for platform in interfaces:
      off, on = get_params(platform, [], False), get_params(platform, [], True)
      if off.steerControlType == structs.CarParams.SteerControlType.angle:
        continue
      assert on.lateralTuning.which() == 'torque', platform
      if off.lateralTuning.which() == 'torque':
        assert on.lateralTuning.torque.to_dict() == off.lateralTuning.torque.to_dict(), platform

  def test_prius_without_zss_keeps_its_deadzone(self):
    eps = structs.CarParams.CarFw(ecu="eps", fwVersion=b'8965B47023\x00\x00\x00\x00\x00\x00', address=0x7a1)
    for nnff in (False, True):
      assert abs(get_params(TOYOTA.TOYOTA_PRIUS, [eps], nnff).lateralTuning.torque.steeringAngleDeadzoneDeg - 0.2) < 1e-6
