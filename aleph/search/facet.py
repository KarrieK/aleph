import six
from followthemoney import model
from exactitude import countries, languages

from aleph.model import Collection


class Facet(object):

    def __init__(self, name, aggregations, parser):
        self.name = name
        self.parser = parser
        self.data = aggregations.get('scoped', {}).get(name, {}).get(name)
        if self.data is None:
            self.data = aggregations.get(name)

    def expand(self, keys):
        pass

    def update(self, result, key):
        pass

    def to_dict(self):
        results = []
        active = list(self.parser.filters.get(self.name, []))
        active.extend(self.parser.post_filters.get(self.name, []))

        for bucket in self.data.get('buckets', []):
            key = six.text_type(bucket.get('key'))
            results.append({
                'id': key,
                'label': key,
                'count': bucket.pop('doc_count', 0),
                'active': key in active
            })
            if key in active:
                active.remove(key)

        for key in active:
            results.insert(0, {
                'id': key,
                'label': key,
                'count': 0,
                'active': True
            })

        self.expand([r.get('id') for r in results])
        for result in results:
            self.update(result, result.get('id'))

        results = sorted(results, key=lambda k: k['count'], reverse=True)
        return {
            'values': results,
        }


class SchemaFacet(Facet):

    def update(self, result, key):
        try:
            result['label'] = model.get(key).plural
        except AttributeError:
            result['label'] = key


class CountryFacet(Facet):

    def update(self, result, key):
        result['label'] = countries.names.get(key, key)


class LanguageFacet(Facet):

    def update(self, result, key):
        result['label'] = languages.names.get(key, key)


class CategoryFacet(Facet):

    def update(self, result, key):
        result['label'] = Collection.CATEGORIES.get(key, key)


class CollectionFacet(Facet):

    def expand(self, keys):
        q = Collection.all_by_ids(keys, authz=self.parser.authz)
        self.collections = q.all()

    def update(self, result, key):
        for collection in self.collections:
            if six.text_type(collection.id) == key:
                result['label'] = collection.label
                result['category'] = collection.category
