"""
Gymnasium env for a 2-car race. The "ego" car is the learning agent; the
"opponent" car is driven by an externally-supplied policy callable (or by
a recorded human trajectory). The same env is used at training time for the
agent and at demo time with a human in the opponent slot.
"""

from __future__ import annotations

from typing import Callable, Optional, Tuple

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from .car import Car, cars_collide
from .domain_rand import DomainRand
from .render import render_first_person
from .track import Track


OPPONENT_POLICY = Callable[[np.ndarray], np.ndarray]
# signature: takes an obs (HxWx3 uint8) and returns (steer, throttle).


class GhostRacerEnv(gym.Env):
    """Ego learns to overtake the opponent. Opponent is supplied externally."""

    metadata = {"render_modes": ["rgb_array"], "render_fps": 30}

    def __init__(
        self,
        opponent_policy: Optional[OPPONENT_POLICY] = None,
        domain_rand: bool = False,
        obs_height: int = 120,
        obs_width: int = 160,
        dt: float = 0.05,
        max_episode_steps: int = 1500,
    ):
        super().__init__()
        self.track = Track()
        self.dt = dt
        self.obs_h = obs_height
        self.obs_w = obs_width
        self.max_episode_steps = max_episode_steps

        self.dr = DomainRand(enabled=domain_rand)
        self.opponent_policy = opponent_policy

        self.ego = Car()
        self.opp = Car()
        self.steps = 0

        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(2,), dtype=np.float32)
        self.observation_space = spaces.Box(
            low=0, high=255, shape=(obs_height, obs_width, 3), dtype=np.uint8
        )

        self._prev_progress_ego = 0.0
        self._prev_progress_opp = 0.0
        self._last_xy_ego: Tuple[float, float] = (0.0, 0.0)
        self._last_xy_opp: Tuple[float, float] = (0.0, 0.0)
        self.lap_ego = 0
        self.lap_opp = 0

    # ------------------------------------------------------------------ API
    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.dr.rng = np.random.default_rng(seed)
        self.dr.resample()

        # Stagger: ego (learner) starts behind so overtaking is the natural objective
        ex, ey, eth = self.track.start_pose(slot=1)
        ox, oy, oth = self.track.start_pose(slot=0)
        self.ego.reset(ex, ey, eth)
        self.opp.reset(ox, oy, oth)

        self.steps = 0
        self.lap_ego = 0
        self.lap_opp = 0
        self._prev_progress_ego = self.track.progress_normalized(*self.ego.position)
        self._prev_progress_opp = self.track.progress_normalized(*self.opp.position)
        self._last_xy_ego = self.ego.position
        self._last_xy_opp = self.opp.position

        return self._obs(self.ego, self.opp), {}

    def step(self, action, opp_action=None):
        """If `opp_action` is supplied (e.g. play.py passing the human's hand
        reading), the opponent's first-person view is NOT rendered, saving the
        most expensive op in the loop.
        """
        action = np.asarray(action, dtype=np.float32).reshape(2)

        if opp_action is not None:
            opp_action = np.asarray(opp_action, dtype=np.float32).reshape(2)
        elif self.opponent_policy is None:
            opp_action = np.array([0.0, 0.4], dtype=np.float32)  # default cruise
        else:
            opp_obs = self._obs(self.opp, self.ego)
            opp_action = np.asarray(self.opponent_policy(opp_obs), dtype=np.float32).reshape(2)

        self.ego.step(action[0], action[1], self.dt)
        self.opp.step(opp_action[0], opp_action[1], self.dt)

        # progress and lap detection
        prog_ego = self._lap_progress(self.ego, self._last_xy_ego, self._prev_progress_ego, "ego")
        prog_opp = self._lap_progress(self.opp, self._last_xy_opp, self._prev_progress_opp, "opp")
        d_ego = prog_ego - (self._prev_progress_ego + self.lap_ego)
        d_opp = prog_opp - (self._prev_progress_opp + self.lap_opp)
        # use raw delta-progress in [0, 1) units of lap; convert to meters
        d_ego_m = d_ego * self.track.total_length
        d_opp_m = d_opp * self.track.total_length

        # reward shaping
        off_track_ego = not self.track.is_on_track(*self.ego.position)
        collision = cars_collide(self.ego, self.opp)

        reward = 0.0
        reward += 1.0 * d_ego_m                            # progress
        reward += 0.5 * (d_ego_m - d_opp_m)                # closing the gap
        reward -= 0.2 if off_track_ego else 0.0            # off-track penalty
        reward -= 1.0 if collision else 0.0                # don't bump

        # overtake bonus: ego's cumulative lap-progress passes opp's
        ego_total = self.lap_ego + prog_ego
        opp_total = self.lap_opp + prog_opp
        prev_ego_total = self.lap_ego + self._prev_progress_ego
        prev_opp_total = self.lap_opp + self._prev_progress_opp
        if (prev_ego_total < prev_opp_total) and (ego_total >= opp_total):
            reward += 5.0  # passed!

        self._prev_progress_ego = prog_ego
        self._prev_progress_opp = prog_opp
        self._last_xy_ego = self.ego.position
        self._last_xy_opp = self.opp.position

        self.steps += 1
        terminated = collision and self.steps > 5
        truncated = self.steps >= self.max_episode_steps

        info = {
            "lap_ego": self.lap_ego,
            "lap_opp": self.lap_opp,
            "off_track": off_track_ego,
            "collision": collision,
            "ego_progress": ego_total,
            "opp_progress": opp_total,
        }
        obs = self._obs(self.ego, self.opp)
        return obs, float(reward), terminated, truncated, info

    # ------------------------------------------------------------------ internal
    def _obs(self, ego: Car, opp: Car) -> np.ndarray:
        return render_first_person(self.track, ego, opp, self.dr, H=self.obs_h, W=self.obs_w)

    def _lap_progress(self, car, last_xy, prev_norm, who: str) -> float:
        """Return current normalized progress; bump lap counter on finish-line crossing."""
        prog = self.track.progress_normalized(*car.position)
        if self.track.finish_line_crossed(last_xy, car.position):
            if who == "ego":
                self.lap_ego += 1
            else:
                self.lap_opp += 1
        return prog

    def render(self):
        from .render import render_spectator
        return render_spectator(self.track, [self.ego, self.opp], self.dr)
