from engine.adaptive_authorization import AdaptiveAuthorizationEngine


def test_low_risk_executes_immediately_in_open_mode():
    engine = AdaptiveAuthorizationEngine()
    decision = engine.authorize(
        'open_brave',
        face_security_enabled=False,
        face_verified=False,
        timestamp=10.0,
    )
    assert decision.execute is True
    assert decision.feedback == 'Executed'
    assert decision.user_state == 'open'
    assert decision.risk_level == 'low'


def test_medium_risk_requires_stability_before_execute():
    engine = AdaptiveAuthorizationEngine()
    t0 = 100.0

    d1 = engine.authorize('switch_tab', face_security_enabled=False, face_verified=False, timestamp=t0)
    d2 = engine.authorize('switch_tab', face_security_enabled=False, face_verified=False, timestamp=t0 + 0.1)

    assert d1.execute is False
    assert d1.feedback == 'Stabilizing...'
    assert d2.execute is True
    assert d2.feedback == 'Executed'


def test_high_risk_restricted_mode_access_controlled_partial_block():
    engine = AdaptiveAuthorizationEngine(restricted_high_risk_actions={'close_window'})
    decision = engine.authorize(
        'close_window',
        face_security_enabled=True,
        face_verified=False,
        timestamp=200.0,
    )
    assert decision.execute is False
    assert decision.feedback == 'Access Controlled'
    assert decision.user_state == 'restricted'
    assert decision.risk_level == 'high'


def test_high_risk_trusted_mode_requires_hold_then_executes():
    engine = AdaptiveAuthorizationEngine()
    t0 = 300.0

    d1 = engine.authorize('double_click', face_security_enabled=True, face_verified=True, timestamp=t0)
    d2 = engine.authorize('double_click', face_security_enabled=True, face_verified=True, timestamp=t0 + 0.15)
    d3 = engine.authorize('double_click', face_security_enabled=True, face_verified=True, timestamp=t0 + 0.25)
    d4 = engine.authorize('double_click', face_security_enabled=True, face_verified=True, timestamp=t0 + 0.50)

    assert d1.feedback == 'Stabilizing...'
    assert d2.feedback in {'Stabilizing...', 'Hold to Confirm'}
    assert d3.feedback == 'Hold to Confirm'
    assert d4.execute is True
    assert d4.feedback == 'Executed'
