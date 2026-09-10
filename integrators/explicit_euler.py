def step(dynamics, t, state, timestep, params):
    """
    Advance state by one timestep using the explicit euler.

    dynamics must accept (t, state, params) and return the time
    derivative of state.
    """
    return state + timestep * dynamics(t, state, params)
