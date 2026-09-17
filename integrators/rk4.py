def step(dynamics, t, state, timestep, params):
    """
    Advance state by one timestep using the fourth order runge-kutta scheme method.

    dynamics must accept (t, state, params) and return the time
    derivative of state.
    """
    k1 = dynamics(t, state, params)
    k2 = dynamics(t + timestep / 2, state + timestep * k1 / 2, params)
    k3 = dynamics(t + timestep / 2, state + timestep * k2 / 2, params)
    k4 = dynamics(t + timestep, state + timestep * k3, params)
    return state + timestep * (k1 + 2 * k2 + 2 * k3 + k4) / 6
