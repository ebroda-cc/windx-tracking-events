from windx_tracking.des import Simulation


def test_schedule_runs_callbacks_in_time_order():
    sim = Simulation()
    order: list[str] = []

    sim.schedule(5, lambda: order.append("b"))
    sim.schedule(1, lambda: order.append("a"))
    sim.schedule(10, lambda: order.append("c"))

    sim.run()

    assert order == ["a", "b", "c"]
    assert sim.now == 10


def test_run_until_stops_early():
    sim = Simulation()
    order: list[str] = []
    sim.schedule(5, lambda: order.append("a"))
    sim.schedule(15, lambda: order.append("b"))

    sim.run(until=10)

    assert order == ["a"]
    assert sim.now == 5


def test_process_yields_delays_and_resumes():
    sim = Simulation()
    log: list[float] = []

    def process():
        log.append(sim.now)
        yield 3
        log.append(sim.now)
        yield 7
        log.append(sim.now)

    sim.process(process())
    sim.run()

    assert log == [0, 3, 10]
