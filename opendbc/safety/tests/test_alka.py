#!/usr/bin/env python3
"""
TOP: tests for ALKA (Always-on Lane Keeping Assist), kept in one place like dragonpilot's test_alka.py.

TOP's ALKA: with ALT_EXP_ALKA set in alternative_experience, steering may stay on while controls aren't
allowed. All the other steering limits (max torque, rate limits, real time limits) still apply.
"""
import unittest

from opendbc.car.lateral import get_max_angle_delta_vm, get_max_angle_vm
from opendbc.car.structs import CarParams
from opendbc.car.tesla.carcontroller import get_safety_CP
from opendbc.car.tesla.values import CarControllerParams as TeslaCarControllerParams
from opendbc.car.vehicle_model import VehicleModel
from opendbc.safety import ALTERNATIVE_EXPERIENCE
from opendbc.safety.tests.libsafety import libsafety_py
from opendbc.safety.tests.common import CANPackerSafety

# a bit next to ALT_EXP_ALKA's (bit 0, reserved): must not act like ALKA
ALT_EXP_NOT_ALKA = 1

# NOTE: test method names are unique across the classes: mutation.py runs one test per method name for core files


class TestALKAToyota(unittest.TestCase):
  """Torque steering (lateral.h steer_torque_cmd_checks)."""
  TX_MSGS: list[list[int]] = []  # for common.SafetyTest.test_tx_hook_on_wrong_safety_mode, like dragonpilot's
  EPS_SCALE = 73
  MAX_RATE_UP = 15

  def setUp(self):
    self.packer = CANPackerSafety("toyota_nodsu_pt_generated")
    self.safety = libsafety_py.libsafety
    self.safety.set_safety_hooks(CarParams.SafetyModel.toyota, self.EPS_SCALE)
    self.safety.init_tests()

  def _tx(self, msg):
    return self.safety.safety_tx_hook(msg)

  def _torque_cmd_msg(self, torque, steer_req=1):
    return self.packer.make_can_msg_safety("STEERING_LKA", 0, {"STEER_TORQUE_CMD": torque, "STEER_REQUEST": steer_req})

  def _set_prev_torque(self, t):
    self.safety.set_desired_torque_last(t)
    self.safety.set_rt_torque_last(t)
    self.safety.set_torque_meas(t, t)

  def test_alka_allows_torque_without_controls(self):
    self.safety.set_controls_allowed(False)
    self._set_prev_torque(0)
    self.assertFalse(self._tx(self._torque_cmd_msg(self.MAX_RATE_UP)))

    self.safety.set_alternative_experience(ALTERNATIVE_EXPERIENCE.ALKA)
    self._set_prev_torque(0)
    self.assertTrue(self._tx(self._torque_cmd_msg(self.MAX_RATE_UP)))

  def test_alka_rate_limits_continue(self):
    # the torque may stay on while controls aren't allowed, so the rate limits keep counting from the last
    # command instead of starting over from zero every frame
    self.safety.set_alternative_experience(ALTERNATIVE_EXPERIENCE.ALKA)
    self.safety.set_controls_allowed(False)
    self._set_prev_torque(0)
    for t in (self.MAX_RATE_UP, 2 * self.MAX_RATE_UP, 3 * self.MAX_RATE_UP):
      self.assertTrue(self._tx(self._torque_cmd_msg(t)))
    # still rate limited
    self.assertFalse(self._tx(self._torque_cmd_msg(5 * self.MAX_RATE_UP)))

    # without ALKA, no torque without controls_allowed
    self.safety.set_alternative_experience(ALTERNATIVE_EXPERIENCE.DEFAULT)
    self._set_prev_torque(3 * self.MAX_RATE_UP)
    self.assertFalse(self._tx(self._torque_cmd_msg(3 * self.MAX_RATE_UP)))

  def test_torque_only_alka_bit(self):
    self.safety.set_alternative_experience(ALT_EXP_NOT_ALKA)
    self.safety.set_controls_allowed(False)
    for t in (-self.MAX_RATE_UP, self.MAX_RATE_UP):
      self._set_prev_torque(t)
      self.assertFalse(self._tx(self._torque_cmd_msg(t)))


class TestALKATesla(unittest.TestCase):
  """Angle steering with the vehicle model limits (lateral.h steer_angle_cmd_checks_vm)."""
  TX_MSGS: list[list[int]] = []
  ANGLE_CONTROL = 1  # DAS_steeringControlType ANGLE_CONTROL

  def setUp(self):
    self.packer = CANPackerSafety("tesla_model3_party")
    self.safety = libsafety_py.libsafety
    self.safety.set_safety_hooks(CarParams.SafetyModel.tesla, 0)
    self.safety.init_tests()

  def _tx(self, msg):
    return self.safety.safety_tx_hook(msg)

  def _angle_cmd_msg(self, angle: float, state: int):
    return self.packer.make_can_msg_safety("DAS_steeringControl", 0, {"DAS_steeringAngleRequest": angle, "DAS_steeringControlType": state})

  def test_alka_allows_steering_without_controls(self):
    self.safety.set_controls_allowed(False)
    self.safety.set_desired_angle_last(0)
    self.assertFalse(self._tx(self._angle_cmd_msg(0, self.ANGLE_CONTROL)))

    self.safety.set_alternative_experience(ALTERNATIVE_EXPERIENCE.ALKA)
    self.safety.set_desired_angle_last(0)
    self.assertTrue(self._tx(self._angle_cmd_msg(0, self.ANGLE_CONTROL)))

  def _rx(self, msg):
    return self.safety.safety_rx_hook(msg)

  def _reset_speed_measurement(self, speed):
    for _ in range(6):  # MAX_SAMPLE_VALS
      self._rx(self.packer.make_can_msg_safety("DI_speed", 0, {"DI_vehicleSpeed": speed * 3.6}))

  def test_alka_lateral_jerk_limit(self):
    # ALKA may steer while controls aren't allowed, but the lateral jerk limit still applies and keeps
    # counting from the last command instead of the measured angle
    self.safety.set_alternative_experience(ALTERNATIVE_EXPERIENCE.ALKA)
    self.safety.set_controls_allowed(False)
    speed = 20.
    self._reset_speed_measurement(speed + 1)  # safety fudges the speed
    max_delta = get_max_angle_delta_vm(speed, VehicleModel(get_safety_CP()), TeslaCarControllerParams)

    self.safety.set_desired_angle_last(0)
    angle = 0.
    for _ in range(3):
      angle += 0.5 * max_delta
      self.assertTrue(self._tx(self._angle_cmd_msg(round(angle, 1), self.ANGLE_CONTROL)))

    # a jump well above the per frame limit is blocked
    self.assertFalse(self._tx(self._angle_cmd_msg(round(angle + 3 * max_delta, 1), self.ANGLE_CONTROL)))

  def test_alka_lateral_accel_limit(self):
    # ALKA may steer while controls aren't allowed, but the lateral accel limit still applies
    self.safety.set_alternative_experience(ALTERNATIVE_EXPERIENCE.ALKA)
    self.safety.set_controls_allowed(False)
    speed = 20.
    self._reset_speed_measurement(speed + 1)  # safety fudges the speed
    max_angle = get_max_angle_vm(speed, VehicleModel(get_safety_CP()), TeslaCarControllerParams)

    too_high = round(1.5 * max_angle, 1)
    self.safety.set_desired_angle_last(round(too_high * 10))  # DEG_TO_CAN, no rate violation
    self.assertFalse(self._tx(self._angle_cmd_msg(too_high, self.ANGLE_CONTROL)))

  def test_angle_only_alka_bit(self):
    self.safety.set_alternative_experience(ALT_EXP_NOT_ALKA)
    self.safety.set_controls_allowed(False)
    self.safety.set_desired_angle_last(0)
    self.assertFalse(self._tx(self._angle_cmd_msg(0, self.ANGLE_CONTROL)))


if __name__ == "__main__":
  unittest.main()
