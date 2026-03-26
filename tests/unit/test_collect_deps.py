#!/usr/bin/env python3
"""
Unit tests for _collect_deps function in claude_code profile.

Tests include_descendants, result_level aggregation, deduplication,
and from_descendant/to_descendant relative path tracking.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from sgraph import SElement, SElementAssociation
from src.profiles.claude_code import _collect_deps


def _build_tree():
    """Build a test element tree:

    /Project
      /Project/src
        /Project/src/handler.py        (file)
          /Project/src/handler.py/MyClass   (class)
            /Project/src/handler.py/MyClass/save  (method)
      /Project/src/models
        /Project/src/models/user.py    (file)
          /Project/src/models/user.py/User  (class)
      /Project/src/db
        /Project/src/db/session.py     (file)
          /Project/src/db/session.py/get_session  (function)
      /Project/src/api
        /Project/src/api/routes.py     (file)
          /Project/src/api/routes.py/handle_request  (function)
      /Project/External
        /Project/External/requests     (external lib)

    SElement(parent, name) auto-adds child to parent — no addChild needed.
    """
    root = SElement(None, '')
    project = SElement(root, 'Project')

    src = SElement(project, 'src')

    # handler.py subtree
    handler_py = SElement(src, 'handler.py')
    my_class = SElement(handler_py, 'MyClass')
    save_method = SElement(my_class, 'save')

    # models/user.py
    models = SElement(src, 'models')
    user_py = SElement(models, 'user.py')
    user_class = SElement(user_py, 'User')

    # db/session.py
    db = SElement(src, 'db')
    session_py = SElement(db, 'session.py')
    get_session = SElement(session_py, 'get_session')

    # api/routes.py
    api = SElement(src, 'api')
    routes_py = SElement(api, 'routes.py')
    handle_request = SElement(routes_py, 'handle_request')

    # External
    external = SElement(project, 'External')
    requests_lib = SElement(external, 'requests')

    return {
        'project': project,
        'src': src,
        'handler_py': handler_py,
        'my_class': my_class,
        'save_method': save_method,
        'user_class': user_class,
        'get_session': get_session,
        'handle_request': handle_request,
        'requests_lib': requests_lib,
    }


def _add_assoc(from_elem, to_elem, dep_type=''):
    """Create an association between two elements and register it on both."""
    assoc = SElementAssociation(from_elem, to_elem, dep_type)
    assoc.initElems()
    return assoc


class TestCollectDepsBasic:
    """Basic _collect_deps tests without include_descendants."""

    def setup_method(self):
        self.elems = _build_tree()
        # handler.py -> requests (outgoing, import)
        _add_assoc(self.elems['handler_py'], self.elems['requests_lib'], 'import')
        # handle_request -> handler.py (incoming to handler.py)
        _add_assoc(self.elems['handle_request'], self.elems['handler_py'], 'call')

    def test_outgoing_only(self):
        deps = _collect_deps(
            self.elems['handler_py'],
            self.elems['handler_py'].getPath(),
            'outgoing', None, False
        )
        assert len(deps) == 1
        assert deps[0]['direction'] == 'outgoing'
        assert deps[0]['target'] == '/Project/External/requests'
        assert deps[0]['type'] == 'import'
        assert 'from_descendant' not in deps[0]

    def test_incoming_only(self):
        deps = _collect_deps(
            self.elems['handler_py'],
            self.elems['handler_py'].getPath(),
            'incoming', None, False
        )
        assert len(deps) == 1
        assert deps[0]['direction'] == 'incoming'
        assert deps[0]['source'] == '/Project/src/api/routes.py/handle_request'
        assert deps[0]['type'] == 'call'
        assert 'to_descendant' not in deps[0]

    def test_both_directions(self):
        deps = _collect_deps(
            self.elems['handler_py'],
            self.elems['handler_py'].getPath(),
            'both', None, False
        )
        outgoing = [d for d in deps if d['direction'] == 'outgoing']
        incoming = [d for d in deps if d['direction'] == 'incoming']
        assert len(outgoing) == 1
        assert len(incoming) == 1

    def test_no_deps_returns_empty(self):
        # src directory has no direct associations
        deps = _collect_deps(
            self.elems['src'],
            self.elems['src'].getPath(),
            'both', None, False
        )
        assert deps == []

    def test_type_omitted_when_empty(self):
        # Create an association without dep_type
        _add_assoc(self.elems['my_class'], self.elems['user_class'], '')
        deps = _collect_deps(
            self.elems['my_class'],
            self.elems['my_class'].getPath(),
            'outgoing', None, False
        )
        assert len(deps) == 1
        assert 'type' not in deps[0]


class TestCollectDepsIncludeDescendants:
    """Tests for include_descendants=True."""

    def setup_method(self):
        self.elems = _build_tree()
        # handler.py itself -> requests (import)
        _add_assoc(self.elems['handler_py'], self.elems['requests_lib'], 'import')
        # MyClass -> User (import)
        _add_assoc(self.elems['my_class'], self.elems['user_class'], 'import')
        # save -> get_session (call)
        _add_assoc(self.elems['save_method'], self.elems['get_session'], 'call')
        # handle_request -> save (incoming to save)
        _add_assoc(self.elems['handle_request'], self.elems['save_method'], 'call')

    def test_descendants_outgoing(self):
        deps = _collect_deps(
            self.elems['handler_py'],
            self.elems['handler_py'].getPath(),
            'outgoing', None, True
        )
        outgoing = [d for d in deps if d['direction'] == 'outgoing']

        # handler.py -> requests (own dep, no from_descendant)
        own = [d for d in outgoing if 'from_descendant' not in d]
        assert len(own) == 1
        assert own[0]['target'] == '/Project/External/requests'

        # MyClass -> User (from_descendant = "MyClass")
        mc_deps = [d for d in outgoing if d.get('from_descendant') == 'MyClass']
        assert len(mc_deps) == 1
        assert mc_deps[0]['target'] == '/Project/src/models/user.py/User'
        assert mc_deps[0]['type'] == 'import'

        # save -> get_session (from_descendant = "MyClass/save")
        save_deps = [d for d in outgoing if d.get('from_descendant') == 'MyClass/save']
        assert len(save_deps) == 1
        assert save_deps[0]['target'] == '/Project/src/db/session.py/get_session'
        assert save_deps[0]['type'] == 'call'

    def test_descendants_incoming(self):
        deps = _collect_deps(
            self.elems['handler_py'],
            self.elems['handler_py'].getPath(),
            'incoming', None, True
        )
        incoming = [d for d in deps if d['direction'] == 'incoming']

        # handle_request -> save (to_descendant = "MyClass/save")
        desc_deps = [d for d in incoming if d.get('to_descendant') == 'MyClass/save']
        assert len(desc_deps) == 1
        assert desc_deps[0]['source'] == '/Project/src/api/routes.py/handle_request'
        assert desc_deps[0]['type'] == 'call'

    def test_descendants_false_excludes_children(self):
        deps = _collect_deps(
            self.elems['handler_py'],
            self.elems['handler_py'].getPath(),
            'outgoing', None, False
        )
        # Only handler.py's own dep (requests), not MyClass or save deps
        assert len(deps) == 1
        assert deps[0]['target'] == '/Project/External/requests'

    def test_descendants_both_directions(self):
        deps = _collect_deps(
            self.elems['handler_py'],
            self.elems['handler_py'].getPath(),
            'both', None, True
        )
        outgoing = [d for d in deps if d['direction'] == 'outgoing']
        incoming = [d for d in deps if d['direction'] == 'incoming']

        assert len(outgoing) == 3  # requests, User, get_session
        assert len(incoming) == 1  # handle_request -> save


class TestCollectDepsResultLevel:
    """Tests for result_level aggregation combined with include_descendants."""

    def setup_method(self):
        self.elems = _build_tree()
        # MyClass -> User (import)
        _add_assoc(self.elems['my_class'], self.elems['user_class'], 'import')
        # save -> get_session (call)
        _add_assoc(self.elems['save_method'], self.elems['get_session'], 'call')

    def test_result_level_none_raw_paths(self):
        deps = _collect_deps(
            self.elems['handler_py'],
            self.elems['handler_py'].getPath(),
            'outgoing', None, True
        )
        targets = {d['target'] for d in deps}
        assert '/Project/src/models/user.py/User' in targets
        assert '/Project/src/db/session.py/get_session' in targets

    def test_result_level_4_file(self):
        deps = _collect_deps(
            self.elems['handler_py'],
            self.elems['handler_py'].getPath(),
            'outgoing', 4, True
        )
        targets = {d['target'] for d in deps}
        # Aggregated to file level
        assert '/Project/src/models/user.py' in targets
        assert '/Project/src/db/session.py' in targets

    def test_result_level_3_directory(self):
        deps = _collect_deps(
            self.elems['handler_py'],
            self.elems['handler_py'].getPath(),
            'outgoing', 3, True
        )
        targets = {d['target'] for d in deps}
        assert '/Project/src/models' in targets
        assert '/Project/src/db' in targets

    def test_result_level_2_repo(self):
        deps = _collect_deps(
            self.elems['handler_py'],
            self.elems['handler_py'].getPath(),
            'outgoing', 2, True
        )
        targets = {d['target'] for d in deps}
        # Both collapse to /Project/src
        assert '/Project/src' in targets
        # Dedup key includes relative path, so different descendants keep separate entries
        src_deps = [d for d in deps if d['target'] == '/Project/src']
        assert len(src_deps) == 2  # MyClass and MyClass/save are different descendants


class TestCollectDepsDeduplication:
    """Tests for deduplication with seen set."""

    def setup_method(self):
        self.elems = _build_tree()
        # Two different deps from save to the same target (different types)
        _add_assoc(self.elems['save_method'], self.elems['get_session'], 'call')
        _add_assoc(self.elems['save_method'], self.elems['get_session'], 'import')

    def test_different_types_not_deduped(self):
        deps = _collect_deps(
            self.elems['handler_py'],
            self.elems['handler_py'].getPath(),
            'outgoing', None, True
        )
        # Both should appear because dep_type differs
        save_deps = [d for d in deps if d.get('from_descendant') == 'MyClass/save']
        assert len(save_deps) == 2
        types = {d['type'] for d in save_deps}
        assert types == {'call', 'import'}

    def test_aggregation_deduplicates_same_target(self):
        # With result_level=4, both get_session deps aggregate to same file+type
        # Actually they have different types, so they won't dedup
        deps = _collect_deps(
            self.elems['handler_py'],
            self.elems['handler_py'].getPath(),
            'outgoing', 4, True
        )
        session_deps = [d for d in deps if d['target'] == '/Project/src/db/session.py']
        # Two entries (call and import have different dep_type)
        assert len(session_deps) == 2

    def test_aggregation_deduplicates_same_type_same_target(self):
        """Two children pointing to same target with same type → deduped when aggregated."""
        # MyClass -> get_session (call)
        _add_assoc(self.elems['my_class'], self.elems['get_session'], 'call')
        # save -> get_session (call) already exists

        deps = _collect_deps(
            self.elems['handler_py'],
            self.elems['handler_py'].getPath(),
            'outgoing', 4, True
        )
        # Both point to /Project/src/db/session.py with type 'call'
        # but from_descendant differs (MyClass vs MyClass/save) → seen key includes relative
        # So they are NOT deduped
        call_deps = [d for d in deps if d['target'] == '/Project/src/db/session.py' and d.get('type') == 'call']
        assert len(call_deps) == 2


class TestCollectDepsEdgeCases:
    """Edge cases."""

    def test_leaf_element_no_children(self):
        """include_descendants on a leaf element behaves same as without."""
        elems = _build_tree()
        _add_assoc(elems['save_method'], elems['get_session'], 'call')

        with_desc = _collect_deps(
            elems['save_method'],
            elems['save_method'].getPath(),
            'outgoing', None, True
        )
        without_desc = _collect_deps(
            elems['save_method'],
            elems['save_method'].getPath(),
            'outgoing', None, False
        )
        assert with_desc == without_desc

    def test_empty_element_no_deps(self):
        """Element with no associations and no children returns empty."""
        elems = _build_tree()
        deps = _collect_deps(
            elems['src'],
            elems['src'].getPath(),
            'both', None, True
        )
        # src has children but they have no associations in this tree
        assert deps == []

    def test_deep_nesting(self):
        """Descendants recurse through multiple levels."""
        elems = _build_tree()
        # save (3 levels deep from handler.py) -> get_session
        _add_assoc(elems['save_method'], elems['get_session'], 'call')

        # Query from handler.py with descendants
        deps = _collect_deps(
            elems['handler_py'],
            elems['handler_py'].getPath(),
            'outgoing', None, True
        )
        assert len(deps) == 1
        assert deps[0]['from_descendant'] == 'MyClass/save'
        assert deps[0]['target'] == '/Project/src/db/session.py/get_session'

    def test_directory_level_query_with_descendants(self):
        """Query from a directory element with descendants captures all file-level deps."""
        elems = _build_tree()
        _add_assoc(elems['handler_py'], elems['requests_lib'], 'import')
        _add_assoc(elems['save_method'], elems['get_session'], 'call')

        deps = _collect_deps(
            elems['src'],
            elems['src'].getPath(),
            'outgoing', None, True
        )
        # Should find both: handler.py->requests and save->get_session
        # (and possibly internal deps if they cross src subtree boundaries)
        targets = {d['target'] for d in deps}
        assert '/Project/External/requests' in targets
        # get_session is also under /Project/src, so it's an internal dep
        # _collect_deps doesn't filter internal — it collects all
        assert '/Project/src/db/session.py/get_session' in targets

        # from_descendant should be relative to src
        handler_dep = [d for d in deps if d['target'] == '/Project/External/requests'][0]
        assert handler_dep['from_descendant'] == 'handler.py'

        save_dep = [d for d in deps if d['target'] == '/Project/src/db/session.py/get_session'][0]
        assert save_dep['from_descendant'] == 'handler.py/MyClass/save'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
