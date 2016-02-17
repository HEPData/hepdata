from hepdata.modules.stats.views import increment, get_count


def test_stats(app):
    increment(1)
    assert (get_count(1)['sum'] == 1)

    increment(1)
    assert (get_count(1)['sum'] == 2)

    # in case of failure, this always returns 1
    assert (get_count(1999)['sum'] == 1)
