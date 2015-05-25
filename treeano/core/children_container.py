import abc

import six
import serialization_state


class ChildrenContainer(six.with_metaclass(abc.ABCMeta, object)):

    """
    API for dealing with the children of nodes (which are also nodes)
    """

    def __eq__(self, other):
        return ((self.__class__ == other.__class__)
                and (self.to_data() == other.to_data()))

    @abc.abstractproperty
    def children(self):
        """
        returns children in the format as expected as the input to the
        container
        """

    @abc.abstractmethod
    def __iter__(self):
        pass

    @abc.abstractmethod
    def to_data(self):
        """
        returns representation of container as data
        """

    @abc.abstractmethod
    def from_data(cls, data):
        """
        converts data representation back into an instance of the appropriate
        class

        NOTE: should be a classmethod
        """


@serialization_state.register_children_container("list")
class ListChildrenContainer(ChildrenContainer):

    """
    contains children as a list
    """

    def __init__(self, children):
        assert isinstance(children, (list, tuple))
        self._children = children

    @property
    def children(self):
        return self._children

    def __iter__(self):
        return (x for x in self.children)

    def to_data(self):
        return [serialization_state.node_to_data(child_node)
                for child_node in self.children]

    @classmethod
    def from_data(cls, data):
        return cls([serialization_state.node_from_data(datum)
                    for datum in data])


@serialization_state.register_children_container("none")
class NoneChildrenContainer(ChildrenContainer):

    """
    contains children as a list
    """

    def __init__(self, children):
        assert children is None

    @property
    def children(self):
        return None

    def __iter__(self):
        return iter([])

    def to_data(self):
        return None

    @classmethod
    def from_data(cls, data):
        return cls(None)


@serialization_state.register_children_container("single_child")
class ChildContainer(ChildrenContainer):

    """
    contains a single child
    """

    def __init__(self, children):
        self.child = children

    @property
    def children(self):
        return self.child

    def __iter__(self):
        return iter([self.child])

    def to_data(self):
        return serialization_state.node_to_data(self.child)

    @classmethod
    def from_data(cls, data):
        return cls(serialization_state.node_from_data(data))


@serialization_state.register_children_container("dict")
class DictChildrenContainer(ChildrenContainer):

    """
    contains children as a dict

    input is a map from string key to value children container
    """

    def __init__(self, children):
        assert isinstance(children, dict)
        for k, v in six.iteritems(children):
            assert isinstance(k, six.string_types)
            assert isinstance(v, ChildrenContainer)
        self._children = children

    @property
    def children(self):
        return self._children

    def __iter__(self):
        return (x
                for children_container in self.children.values()
                for x in children_container)

    def to_data(self):
        return {k: serialization_state.children_container_to_data(v)
                for k, v in six.iteritems(self.children)}

    @classmethod
    def from_data(cls, data):
        return cls({k: serialization_state.children_container_from_data(v)
                    for k, v in six.iteritems(data)})


class DictChildrenContainerSchema(object):

    """
    helper class for constructing DictChildrenContainer's given a schema

    eg.
    dccs = DictChildrenContainerSchema(
      foo=ListChildrenContainer,
      bar=ChildContainer,
    )
    # note how the values do not need to be converted into the appropriate
    # ChildrenContainer instances manually
    dccs({"foo": [ANode(), BNode()], "bar": CNode()})
    """

    def __init__(self, **schema):
        for k, v in six.iteritems(schema):
            assert isinstance(k, six.string_types)
            assert ChildrenContainer in v.__bases__
        self.schema = schema

    def __call__(self, children):
        assert children.keys() == self.schema.keys()
        new_children = {}
        for k in children:
            new_children[k] = self.schema[k](children[k])
            assert isinstance(new_children[k], ChildrenContainer)
        return DictChildrenContainer(new_children)