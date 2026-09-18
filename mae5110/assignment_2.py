from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation, PillowWriter

from integrators import rk4
from models import inverted_pendulum_walker as model


def compute_ankle_torque(state, params):
    theta, velocity = state
    g, length, mass = params["gravity"], params["length"], params["mass"]
    kp = g / length
    kd = 2 * np.sqrt(kp)
    torque = mass * length**2 * (-kp * np.sin(theta) - kp * theta - kd * velocity)
    return np.clip(torque, -0.1 * mass * g * length, 0.05 * mass * g * length)


def balancing_dynamics(t, state, params):
    controlled_params = {**params, "ankle_torque": compute_ankle_torque(state, params)}
    return model.dynamics(t, state, controlled_params)


@dataclass
class RegionOfAttraction:
    angles: np.ndarray
    velocities: np.ndarray
    converged: np.ndarray

    def contains(self, state):
        theta, velocity = state
        if not (
            self.angles[0] <= theta <= self.angles[-1]
            and self.velocities[0] <= velocity <= self.velocities[-1]
        ):
            return False
        i = np.clip(
            np.searchsorted(self.angles, theta, side="right") - 1,
            0,
            len(self.angles) - 2,
        )
        j = np.clip(
            np.searchsorted(self.velocities, velocity, side="right") - 1,
            0,
            len(self.velocities) - 2,
        )
        return bool(self.converged[i : i + 2, j : j + 2].all())


def estimate_roa(params, *, grid_size=161, dt=0.01, duration=12.0, tolerance=1e-3):

    gamma = params["incline"]
    angles = np.linspace(gamma - np.pi / 2, gamma + np.pi / 2, grid_size)
    vmax = np.sqrt(2 * params["gravity"] / params["length"])
    velocities = np.linspace(-vmax, vmax, grid_size)
    theta, velocity = np.meshgrid(angles, velocities, indexing="ij")
    states = np.array([theta.ravel(), velocity.ravel()])
    alive = np.cos(states[0] - gamma) > 1e-12
    n_steps = int(np.ceil(duration / dt))
    dt = duration / n_steps
    for step in range(n_steps):
        indices = np.flatnonzero(alive)
        if not indices.size:
            break
        states[:, indices] = rk4.step(
            balancing_dynamics, step * dt, states[:, indices], dt, params
        )
        alive[indices] = (
            np.isfinite(states[:, indices]).all(axis=0)
            & (states[0, indices] > angles[0])
            & (states[0, indices] < angles[-1])
        )
    converged = (
        alive & (np.abs(states[0]) < tolerance) & (np.abs(states[1]) < tolerance)
    )
    return RegionOfAttraction(angles, velocities, converged.reshape(theta.shape))


def roa_event_guard(state, roa):
    return roa.contains(state)


def simulate_walker(initial_state, params, roa, *, dt=1e-3, duration=10.0):

    state = np.asarray(initial_state, dtype=float).copy()
    # Walking stays passive until the terminal RoA guard fires.
    walking_params = {**params, "ankle_torque": 0.0}
    times, states = [0.0], [state.copy()]
    completed_steps = 0
    if roa_event_guard(state, roa):
        return np.array(times), np.array(states).T, completed_steps, "captured"
    for _ in range(int(np.ceil(duration / dt))):
        t = times[-1]
        step_dt = min(dt, duration - t)
        next_state = rk4.step(model.dynamics, t, state, step_dt, walking_params)
        captured = roa_event_guard(next_state, roa)
        if not captured and model.event_guard(state, next_state, params):
            next_state = model.event_dynamics(next_state, params)
            completed_steps += 1
            captured = roa_event_guard(next_state, roa)
        times.append(t + step_dt)
        states.append(next_state.copy())
        if captured:
            reason = "captured"
            break
        if (
            not params["incline"] - np.pi / 2
            < next_state[0]
            < params["incline"] + np.pi / 2
        ):
            reason = "fell"
            break
        state = next_state
    else:
        reason = "time limit"
    return np.array(times), np.array(states).T, completed_steps, reason


def main():
    params = model.generate_params()
    roa = estimate_roa(params)
    time_traj, state_traj, steps, reason = simulate_walker([0.0, 3.0], params, roa)
    output = Path("output/assignment_2")
    output.mkdir(parents=True, exist_ok=True)

    fig_roa, ax_roa = plt.subplots(layout="constrained")
    ax_roa.pcolormesh(
        roa.angles,
        roa.velocities,
        roa.converged.T,
        shading="nearest",
        cmap="Greens",
        vmin=0,
        vmax=1,
    )
    ax_roa.plot(*state_traj, color="tab:blue", linewidth=1, label="Passive walker")
    ax_roa.plot(*state_traj[:, -1], "ro", label=reason)
    ax_roa.set(
        xlabel="Angle (rad)",
        ylabel="Angular velocity (rad/s)",
        title="Estimated ankle-controller RoA (green)",
    )
    ax_roa.legend()
    fig_roa.savefig(output / "roa.png", dpi=180)

    fig, ax = plt.subplots(figsize=(8, 5), layout="constrained")

    def draw_frame(index):
        # The massless swing leg is repositioned instantaneously at each impact.
        model.visualize(state_traj[:, index], {**params, "ankle_torque": 0.0}, ax=ax)
        ax.set_title(f"t = {time_traj[index]:.2f} s; {reason}")

    # Simulate at a small timestep, but render only 25 frames per second.
    fps = 25
    frame_indices = list(range(0, time_traj.size, round(1 / (fps * 1e-3))))
    if frame_indices[-1] != time_traj.size - 1:
        frame_indices.append(time_traj.size - 1)
    animation = FuncAnimation(
        fig, draw_frame, frames=frame_indices, interval=1000 / fps, repeat=False
    )
    animation.save(output / "walker.gif", writer=PillowWriter(fps=fps))
    # To save an MP4 instead, install FFmpeg and use:
    # animation.save(output / "walker.mp4", writer="ffmpeg", fps=fps)
    print(f"{reason} at {time_traj[-1]:.3f} s ({steps} footstrikes).")
    print(f"Saved {output / 'roa.png'} and {output / 'walker.gif'}.")
    plt.show()


if __name__ == "__main__":
    main()
