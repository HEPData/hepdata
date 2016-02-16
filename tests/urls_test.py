from hepdata.utils.url import modify_query


def test_url_modify(app):
    with app.app_context():

        url_path = modify_query('es_search.search', **{'date': '2001, 2002'})
        assert(url_path == '/search/?date=2001%2C+2002')

        url_path = modify_query('es_search.search', **{'date': '2001, 2002', 'q': 'elastic scattering'})
        assert(url_path == '/search/?date=2001%2C+2002&q=elastic+scattering')

        url_path = modify_query('es_search.search', **{'date': None, 'q': 'elastic scattering'})
        assert(url_path == '/search/?q=elastic+scattering')
