def pytest_configure(config):
    config.addinivalue_line('markers', 'docker: needs Docker and the zaklang-sandbox image; CI runs -m "not docker"')
