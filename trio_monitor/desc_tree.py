import typing
from typing import Any, Dict, Optional, TypeVar, Union, cast

from rich.console import Console, ConsoleOptions, RenderResult
from rich.tree import Tree

from .protocol import TrioNursery, TrioTask
from .registry import RegisteredSCInfo, SCRegistry

""" Description Tree

    We trace the current system state by keeping our own task tree

    This tree must support:
    1. Build up a state tree based on the trio node given
    2. Given a task, find it's parent
    3. Given another tree, find the first node which is different
    4. Operations for adding/removing a single node to/from tree
"""


TrioNode = TypeVar("TrioNode", TrioNursery, TrioTask)


class DescNode:
    def __init__(self, node: TrioNode, registry: SCRegistry):
        self.parent: Optional[DescNode] = None
        self.children: typing.List[DescNode] = []
        self._registry: SCRegistry = registry

        # ref to the actual node
        self.ref: typing.Union[TrioTask, TrioNursery] = node

    @property
    def info(self) -> RegisteredSCInfo:
        return self._registry.get_info(self.ref)

    def __repr__(self):
        return f"<DescNode:{self.info.name}: {self.children}>"

    def _rich_node(self, parent: Tree):
        cur_node = parent.add(f"[yellow] name: {self.info.name}")
        [n._rich_node(parent=cur_node) for n in self.children]


class DescTree:
    def __init__(self, root, registry: Optional[SCRegistry]):
        self.root: DescNode = root

        reg: Any = SCRegistry() if registry == None else registry
        self._registry: SCRegistry = reg

        self.ref_2node: Dict[Union[TrioTask, TrioNursery], DescNode] = {}

        # only used for debugging
        self._nodes: Dict[str, DescNode] = {}

    @property
    def registry(self):
        return self._registry

    def node_by_name(self, name: str) -> Optional[DescNode]:
        """Get a description node by its name
        only used for debugging
        """
        return self._nodes.get(name, None)

    def __repr__(self):
        return f"{self.root}"

    @classmethod
    def build(
        cls, root_task: TrioTask, registry: Optional[SCRegistry] = None
    ) -> "DescTree":
        """Build a tree of from source"""

        _registry: SCRegistry = SCRegistry() if registry is None else registry

        root_desc = DescNode(root_task, _registry)

        tree = cls(root=root_desc, registry=_registry)

        def register(node: DescNode):
            name = tree._registry.get_name(node.ref)
            tree.ref_2node[node.ref] = node

            # only used for debugging
            tree._nodes[name] = node

        def build_task(task_desc: DescNode):
            task = cast(TrioTask, task_desc.ref)
            # build for it's child nurseries
            for n in task.child_nurseries:
                child_desc = DescNode(node=n, registry=_registry)
                child_desc.parent = task_desc
                task_desc.children.append(child_desc)
                register(child_desc)
                build_nursery(child_desc)

        def build_nursery(nursery_desc: DescNode):
            nursery = cast(TrioNursery, nursery_desc.ref)
            # build for it's child tasks
            for t in nursery.child_tasks:
                child_desc = DescNode(node=t, registry=_registry)
                child_desc.parent = nursery_desc
                nursery_desc.children.append(child_desc)
                register(child_desc)
                build_task(child_desc)

        register(root_desc)
        build_task(root_desc)
        return tree

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        """Support Python `rich` lib"""
        root = Tree("DescTree")
        self.root._rich_node(parent=root)
        yield root

    def get_parent_nursery(self, task: TrioTask) -> Optional[TrioNursery]:
        """Directly retrieve the parent nursery of a task"""
        node = self.ref_2node.get(task, None)
        if node is not None:
            if node.parent is not None:
                nursery = cast(TrioNursery, node.parent.ref)
                return nursery
        return None

    def find_parent_nursery_from_trio(self, target: TrioTask) -> Optional[TrioNursery]:
        """Return the parent nursery of the target task from trio's internal task tree
        Warning: O(n) time complexity"""

        def find_parent_nursery(
            tree_root: TrioTask,
            target: TrioTask,
        ):
            for n in tree_root.child_nurseries:
                if target in n.child_tasks:
                    return n
                else:
                    for t in n.child_tasks:
                        nursery = find_parent_nursery(t, target)
                        if nursery:
                            return nursery
            return None

        # root.ref point to the root of a trio task tree
        nursery = find_parent_nursery(cast(TrioTask, self.root.ref), target)
        return nursery

    def ensure_node_in_tree(self, node: DescNode):
        if node != self._nodes[node.info.name]:
            raise RuntimeError(f"bug: node not exists in tree: {node}")
        if self.ref_2node.get(node.ref, None) is None:
            raise RuntimeError(f"bug: ref not exists in tree: {node.ref}")

    def ensure_node_not_in_tree(self, node: DescNode):
        if node in self._nodes:
            raise RuntimeError(f"bug: node already exists in tree: {node}")
        if self.ref_2node.get(node.ref, None) is not None:
            raise RuntimeError(f"bug: ref already exists in tree: {node.ref}")

    def remove_node(self, node: DescNode):
        """Remove node and all of it's children from Desc tree,
        also break the link to it's parent"""

        print(f"[remove] receive node: {node}")
        self.ensure_node_in_tree(node)
        self.ref_2node.pop(node.ref)
        self._nodes.pop(node.info.name)

        # unregister all children in the tree
        for child in node.children:
            self.remove_node(child)

        if node.parent:
            node.parent.children.remove(node)
            # if we remove the only task from parent nursery,
            # the parent nursery should also be removed automatically
            # sinc Trio only notify us the creation/removement of tasks, but not nurseries
            if len(node.parent.children) == 0:
                self.remove_node(node.parent)
            node.parent = None

        self._registry.remove(node.ref)

    # def add_node(self, node: DescNode, parent: DescNode):
    #     self.ensure_node_in_tree(parent)
    #     self.ensure_node_not_in_tree(node)

    #     if node in parent.children:
    #         raise RuntimeError(f"bug add same child({node}) to parent{parent}")
    #     node.parent = parent
    #     parent.children.append(node)

    #     self.ref_2node[node.ref] = node
    #     self.nodes[node.name] = node
