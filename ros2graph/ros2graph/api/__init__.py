# Software License Agreement (proprietary)
#
# @author    Guillaume Autran <gautran@clearpath.ai>
# @copyright (c) 2023, Clearpath Robotics, Inc., All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, is not permitted without the
# express permission of Clearpath Robotics.

from collections import namedtuple
from typing import Any
from typing import List
import sys

from rclpy.node import HIDDEN_NODE_PREFIX
from ros2cli.node.strategy import NodeStrategy


NodeName = namedtuple('NodeName', ('name', 'namespace', 'full_name', 'id'))
TopicInfo = namedtuple('Topic', ('name', 'types'))


def _is_hidden_name(name):
    # note, we're assuming the hidden node prefix is the same for other hidden names
    return any(part.startswith(HIDDEN_NODE_PREFIX) for part in name.split('/'))


def get_absolute_node_name(node_name):
    if not node_name:
        return None
    if node_name[0] != '/':
        node_name = '/' + node_name
    return node_name


def parse_node_name(node_name):
    full_node_name = node_name
    if not full_node_name.startswith('/'):
        full_node_name = '/' + full_node_name
    namespace, node_basename = full_node_name.rsplit('/', 1)
    if namespace == '':
        namespace = '/'
    return NodeName(node_basename, namespace, full_node_name, get_id('node_'))


def has_duplicates(values: List[Any]) -> bool:
    """Find out if there are any exact duplicates in a list of strings."""
    return len(set(values)) < len(values)


g_id = 0


def get_id(s):
    global g_id
    g_id = g_id + 1
    return s + str(g_id)


def get_node_names(*, node, include_hidden_nodes=False):
    node_names_and_namespaces = node.get_node_names_and_namespaces()
    return [
        NodeName(
            name=t[0],
            namespace=t[1],
            full_name=t[1] + ('' if t[1].endswith('/') else '/') + t[0],
            id=get_id('node_'),
        )
        for idx, t in enumerate(node_names_and_namespaces)
        if (
            include_hidden_nodes or
            (t[0] and not t[0].startswith(HIDDEN_NODE_PREFIX))
        )
    ]


def get_topics(remote_node_name, func, *, include_hidden_topics=False):
    node = parse_node_name(remote_node_name)
    names_and_types = func(node.name, node.namespace)
    return [
        TopicInfo(
            name=t[0],
            types=t[1])
        for t in names_and_types if include_hidden_topics or not _is_hidden_name(t[0])]


def get_subscriber_info(*, node, remote_node_name, include_hidden=False):
    return get_topics(
        remote_node_name,
        node.get_subscriber_names_and_types_by_node,
        include_hidden_topics=include_hidden
    )


def get_publisher_info(*, node, remote_node_name, include_hidden=False):
    return get_topics(
        remote_node_name,
        node.get_publisher_names_and_types_by_node,
        include_hidden_topics=include_hidden
    )


def get_service_client_info(*, node, remote_node_name, include_hidden=False):
    return get_topics(
        remote_node_name,
        node.get_client_names_and_types_by_node,
        include_hidden_topics=include_hidden
    )


def get_service_server_info(*, node, remote_node_name, include_hidden=False):
    return get_topics(
        remote_node_name,
        node.get_service_names_and_types_by_node,
        include_hidden_topics=include_hidden
    )


def get_action_server_info(*, node, remote_node_name, include_hidden=False):
    remote_node = parse_node_name(remote_node_name)
    names_and_types = node.get_action_server_names_and_types_by_node(
        remote_node.name, remote_node.namespace)
    return [
        TopicInfo(
            name=n,
            types=t)
        for n, t in names_and_types if include_hidden or not _is_hidden_name(n)]


def get_action_client_info(*, node, remote_node_name, include_hidden=False):
    remote_node = parse_node_name(remote_node_name)
    names_and_types = node.get_action_client_names_and_types_by_node(
        remote_node.name, remote_node.namespace)
    return [
        TopicInfo(
            name=n,
            types=t)
        for n, t in names_and_types if include_hidden or not _is_hidden_name(n)]


def sorted_iteritems(d):
    # Used mostly for result reproducibility (while testing.)
    keys = list(d.keys())
    keys.sort()
    for key in keys:
        value = d[key]
        yield key, value


class NodeNameCompleter:
    """Callable returning a list of node names."""

    def __init__(self, *, include_hidden_nodes_key=None):
        self.include_hidden_nodes_key = include_hidden_nodes_key

    def __call__(self, prefix, parsed_args, **kwargs):
        include_hidden_nodes = getattr(
            parsed_args, self.include_hidden_nodes_key) \
            if self.include_hidden_nodes_key else False
        with NodeStrategy(parsed_args) as node:
            return [
                n.full_name for n in get_node_names(
                    node=node, include_hidden_nodes=include_hidden_nodes)]


class DotWriter:
    '''DOT syntax can be found here: https://graphviz.org/doc/info/lang.html'''

    def __init__(self, fp=sys.stdout):
        self._fp = fp

    def begin_graph(self, **attrs):
        self.write('digraph {\n')

        for name, value in sorted_iteritems(attrs):
            if value is None:
                continue
            self.write("\t")
            self.key_value(name, value)
            self.write(';\n')

    def end_graph(self):
        self.write('}\n')

    def begin_subgraph(self, subgraph, **attrs):
        self.write('subgraph ')
        self.id(subgraph)
        self.write(' {\n')
        for name, value in sorted_iteritems(attrs):
            if value is None:
                continue
            self.write("\t")
            self.key_value(name, value)
            self.write(';\n')

    def end_subgraph(self):
        self.write('}\n')

    def attr(self, what, **attrs):
        self.write("\t")
        self.write(what)
        self.attr_list(attrs)
        self.write(";\n")

    def node(self, node, **attrs):
        self.write("\t")
        self.id(node)
        self.attr_list(attrs)
        self.write(";\n")

    def edge(self, src, dst, **attrs):
        self.write("\t")
        self.id(src)
        self.write(" -> ")
        self.id(dst)
        self.attr_list(attrs)
        self.write(";\n")

    def attr_list(self, attrs):
        if not attrs:
            return
        self.write(' [')
        first = True
        for name, value in sorted_iteritems(attrs):
            if value is None:
                continue
            if first:
                first = False
            else:
                self.write(", ")
            self.key_value(name, value)
        self.write(']')

    def key_value(self, key, value):
        self.id(key)
        self.write('=')
        self.id(value)

    def id(self, id):
        if isinstance(id, (int, float)):
            s = str(id)
        elif isinstance(id, str):
            if id.isalnum() and not id.startswith('0x'):
                s = id
            else:
                s = self.escape(id)
        else:
            raise TypeError
        self.write(s)

    def clean(self, dirty):
        return ''.join(e if e.isalnum() else '_' for e in dirty)

    def color(self, rgb):
        r, g, b = rgb

        def float2int(f):
            if f <= 0.0:
                return 0
            if f >= 1.0:
                return 255
            return int(255.0*f + 0.5)

        return "#" + "".join(["%02x" % float2int(c) for c in (r, g, b)])

    def escape(self, s):
        s = s.replace('\\', r'\\')
        s = s.replace('\n', r'\n')
        s = s.replace('\t', r'\t')
        s = s.replace('"', r'\"')
        return '"' + s + '"'

    def write(self, s, with_nl=True):
        self._fp.write(s)