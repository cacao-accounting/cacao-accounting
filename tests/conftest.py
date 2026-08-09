def pytest_addoption(parser):
    parser.addoption("--slow", action="store", default="False", help="Run all tests, even those that take the longest.")
    parser.addoption(
        "--full",
        action="store_true",
        default=False,
        help="Run and report full end-to-end business-cycle tests.",
    )
