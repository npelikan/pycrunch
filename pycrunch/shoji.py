"""JSONObject and Element subclasses for Shoji objects.

See https://bitbucket.org/fumanchu/shoji/src/tip/spec.txt?at=default
for the latest Shoji specification.
"""

import json

from pycrunch import elements


class Tuple(elements.JSONObject):
    """A Shoji Tuple of attributes.

    Shoji Catalogs have an 'index' member, which maps URL's to Tuples.
    Shoji Entities have a 'body' member which is a Tuple.

    Like all JSONObjects, the items in a Tuple are readable as keys
    (e.g. tup['foo']) or as attributes (e.g. tup.foo). In addition,
    the URL of the Entity (whether from Catalog.index or Entity.self)
    is included as Tuple.entity_url. The Tuple.fetch method then assumes
    .entity_url as the URL to request, and either returns the complete
    Entity or raises TypeError if the response could not be parsed.
    """

    def __init__(self, session, entity_url, **members):
        self.session = session
        self.entity_url = entity_url
        super(Tuple, self).__init__(**members)

    def copy(self):
        """Return a (shallow) copy of self."""
        return self.__class__(self.session, self.entity_url, **self)

    def fetch(self, *args, **kwargs):
        r = self.session.get(self.entity_url, *args, **kwargs)
        if r.payload is None:
            raise TypeError("Response could not be parsed.", r)
        return r.payload


class Document(elements.Element):
    """A base class for Shoji Documents."""

    navigation_collections = ()

    def __getattr__(self, key):
        # Return the requested attribute if present in self.keys
        v = self.get(key, elements.omitted)
        if v is not elements.omitted:
            return v

        # If the requested attribute is present in a URL collection,
        # do a GET and return its payload.
        for collname in self.navigation_collections:
            coll = self.get(collname, {})
            if key in coll:
                return self.session.get(coll[key]).payload

        raise AttributeError(
            "%s has no attribute %s" % (self.__class__.__name__, key))

    def post(self, *args, **kwargs):
        kwargs.setdefault('headers', {})
        kwargs["headers"].setdefault("Content-Type", "application/json")
        return self.session.post(self.self, *args, **kwargs)

    def patch(self, *args, **kwargs):
        kwargs.setdefault('headers', {})
        kwargs["headers"].setdefault("Content-Type", "application/json")
        return self.session.patch(self.self, *args, **kwargs)


class Catalog(Document):
    """A Shoji Catalog."""

    element = "shoji:catalog"
    navigation_collections = ("catalogs", "views", "urls")

    def __init__(__this__, session, **members):
        if 'index' in members:
            members['index'] = dict(
                (entity_url, Tuple(session, entity_url, **tup))
                for entity_url, tup in members['index'].iteritems()
            )
        super(Catalog, __this__).__init__(session, **members)

    def create(self, entity=None, refresh=None):
        """POST the given Entity to this catalog to create a new resource.

        An entity is returned. If 'refresh' is:

            * True: an additional GET is performed and the Entity it fetches
              is returned (which is assumed to have the correct "self" member).
            * False: no additional GET is performed, and a minimal Entity
              is returned; either way, its "self" member is set to the URL
              of the newly-created resource.
            * None (the default): If an Entity was provided, behave like
              'refresh' was False. If not provided, behave like 'refresh'
              was True.
        """
        if refresh is None:
            refresh = (entity is None)

        if entity is None:
            entity = Entity(self.session)

        r = self.post(data=entity.json)
        new_url = r.headers["Location"]

        if refresh:
            entity = self.session.get(new_url).payload
        else:
            entity.self = new_url

        return entity

    def by(self, attr):
        """Return the Tuples of self.index indexed by the given 'attr' instead.

        If a given Tuple does not contain the specified attribute,
        it is not included. If more than one does, only one will be
        included (which one is undefined).

        The specified attr is not popped from the Tuple; it is merely
        copied to the output keys. Due to restrictions on Python dicts,
        specifying attrs which are not hashable will raise an error.
        """
        return elements.JSONObject(**dict(
            (tupl[attr], tupl)
            for tupl in self.index.itervalues()
            if attr in tupl
        ))

    def add(self, entity_url, attrs=None):
        """Add the given entity, plus any catalog attributes, to self."""
        index = {entity_url: attrs or {}}
        return super(Catalog, self).patch(data=json.dumps(index)).payload


class Entity(Document):

    element = "shoji:entity"
    navigation_collections = ("catalogs", "fragments", "views", "urls")

    def __init__(__this__, session, **members):
        members.setdefault("body", {})
        if 'self' in members:
            members['body'] = Tuple(session, members['self'], **members['body'])
        super(Entity, __this__).__init__(session, **members)


class View(Document):

    element = "shoji:view"
    navigation_collections = ("views", "urls")
