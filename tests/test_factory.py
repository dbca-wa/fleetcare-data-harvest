def test_config(app):
    assert app.testing
    assert app.debug
