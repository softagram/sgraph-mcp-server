#!/usr/bin/env python3
"""
Unit tests for SecurityService.

Tests all 6 security audit dimensions with synthetic sgraph models.
"""

import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from sgraph import SGraph
from src.services.security_service import SecurityService


# ---------------------------------------------------------------------------
# Fixture helpers: build synthetic SGraph models for each dimension
# ---------------------------------------------------------------------------

def _make_empty_model():
    """Model with just a repository, no security data."""
    g = SGraph()
    repo = g.createOrGetElementFromPath('/Project/repo')
    repo.setType('repository')
    src = g.createOrGetElementFromPath('/Project/repo/src')
    src.setType('dir')
    f = g.createOrGetElementFromPath('/Project/repo/src/main.py')
    f.setType('file')
    return g


def _make_model_with_secrets():
    """Model with 3 secrets across 2 repos.

    repo-a: 2 secrets (both Hex High Entropy String)
    repo-b: 1 secret (no secret_type set -> should map to 'unknown')
    """
    g = SGraph()
    repo_a = g.createOrGetElementFromPath('/Project/repo-a')
    repo_a.setType('repository')
    repo_b = g.createOrGetElementFromPath('/Project/repo-b')
    repo_b.setType('repository')

    s1 = g.createOrGetElementFromPath('/Project/repo-a/src/config.py/secret1')
    s1.setType('potential_secret')
    s1.addAttribute('secret_type', 'Hex High Entropy String')

    s2 = g.createOrGetElementFromPath('/Project/repo-a/src/config.py/secret2')
    s2.setType('potential_secret')
    s2.addAttribute('secret_type', 'Hex High Entropy String')

    s3 = g.createOrGetElementFromPath('/Project/repo-b/src/settings.py/secret3')
    s3.setType('potential_secret')
    # No secret_type attribute => should become 'unknown'

    return g


def _make_model_with_vulnerabilities():
    """Model with 3 vulnerabilities: 1 critical, 1 high, 1 moderate."""
    g = SGraph()
    repo = g.createOrGetElementFromPath('/Project/repo')
    repo.setType('repository')

    v1 = g.createOrGetElementFromPath('/Project/repo/External/Python/requests/CVE-2023-001')
    v1.setType('vulnerability')
    v1.addAttribute('severity', 'critical')

    v2 = g.createOrGetElementFromPath('/Project/repo/External/Python/flask/CVE-2023-002')
    v2.setType('vulnerability')
    v2.addAttribute('severity', 'high')

    v3 = g.createOrGetElementFromPath('/Project/repo/External/Python/urllib3/CVE-2023-003')
    v3.setType('vulnerability')
    v3.addAttribute('severity', 'moderate')

    return g


def _make_model_with_outdated():
    """Model with outdated dependencies and a framework deprecation.

    1 fully outdated TFM, 1 almost outdated TFM, 1 framework_deprecation element.
    """
    g = SGraph()
    repo = g.createOrGetElementFromPath('/Project/repo')
    repo.setType('repository')

    # Fully outdated
    pkg1 = g.createOrGetElementFromPath('/Project/repo/External/Python/django')
    pkg1.addAttribute('outdated', 'fully')
    pkg1.addAttribute('end_of_life', '2024-01-01')

    # Almost outdated
    pkg2 = g.createOrGetElementFromPath('/Project/repo/External/Python/flask')
    pkg2.addAttribute('outdated', 'almost')
    pkg2.addAttribute('end_of_life', '2025-06-01')

    # Framework deprecation
    dep1 = g.createOrGetElementFromPath('/Project/repo/src/legacy_module/deprecation1')
    dep1.setType('framework_deprecation')
    dep1.addAttribute('description', 'jQuery 1.x is deprecated')

    return g


def _make_model_with_risk():
    """Model with risk metrics on dirs/repos.

    repo: risk_density=250.5, softagram_index=35, loc=10000
    big_dir: risk_density=300, softagram_index=28, loc=8000
    small_dir: risk_density=999, softagram_index=5, loc=50 (below 100 LOC threshold)
    """
    g = SGraph()
    repo = g.createOrGetElementFromPath('/Project/repo')
    repo.setType('repository')
    repo.addAttribute('risk_density', '250.5')
    repo.addAttribute('softagram_index', '35')
    repo.addAttribute('architecture_modularity', '60')
    repo.addAttribute('loc', '10000')

    big_dir = g.createOrGetElementFromPath('/Project/repo/src/core')
    big_dir.setType('dir')
    big_dir.addAttribute('risk_density', '300')
    big_dir.addAttribute('softagram_index', '28')
    big_dir.addAttribute('architecture_modularity', '55')
    big_dir.addAttribute('loc', '8000')

    # Small dir should be filtered out (loc < 100)
    small_dir = g.createOrGetElementFromPath('/Project/repo/src/tiny')
    small_dir.setType('dir')
    small_dir.addAttribute('risk_density', '999')
    small_dir.addAttribute('softagram_index', '5')
    small_dir.addAttribute('architecture_modularity', '10')
    small_dir.addAttribute('loc', '50')

    return g


def _make_model_with_backstage():
    """Model with 3 backstage-annotated services.

    svc-a: production, team-alpha, exposed to public
    svc-b: deprecated, team-alpha, NOT exposed
    svc-c: production, team-beta, NOT exposed
    """
    g = SGraph()
    repo = g.createOrGetElementFromPath('/Project/repo')
    repo.setType('repository')

    svc_a = g.createOrGetElementFromPath('/Project/repo/service-a')
    svc_a.addAttribute('backstage__spec__owner', 'team-alpha')
    svc_a.addAttribute('backstage__spec__lifecycle', 'production')
    svc_a.addAttribute('backstage__metadata__tags__exposed_to_public', 'true')

    svc_b = g.createOrGetElementFromPath('/Project/repo/service-b')
    svc_b.addAttribute('backstage__spec__owner', 'team-alpha')
    svc_b.addAttribute('backstage__spec__lifecycle', 'deprecated')

    svc_c = g.createOrGetElementFromPath('/Project/repo/service-c')
    svc_c.addAttribute('backstage__spec__owner', 'team-beta')
    svc_c.addAttribute('backstage__spec__lifecycle', 'production')

    return g


def _make_model_with_bus_factor():
    """Model with files having author count data.

    critical.py: loc=3000, author_count_365=1  (single-author, large -> flagged)
    tiny.py:     loc=50,   author_count_365=1  (single-author, small -> NOT flagged)
    shared.py:   loc=2000, author_count_365=5  (multi-author -> not flagged)

    All in same repo. Weighted avg author count:
      (1*3000 + 1*50 + 5*2000) / (3000 + 50 + 2000) = 13050/5050 ~ 2.58
    """
    g = SGraph()
    repo = g.createOrGetElementFromPath('/Project/repo')
    repo.setType('repository')

    f1 = g.createOrGetElementFromPath('/Project/repo/src/critical.py')
    f1.setType('file')
    f1.addAttribute('loc', '3000')
    f1.addAttribute('author_count_365', '1')

    f2 = g.createOrGetElementFromPath('/Project/repo/src/tiny.py')
    f2.setType('file')
    f2.addAttribute('loc', '50')
    f2.addAttribute('author_count_365', '1')

    f3 = g.createOrGetElementFromPath('/Project/repo/src/shared.py')
    f3.setType('file')
    f3.addAttribute('loc', '2000')
    f3.addAttribute('author_count_365', '5')

    return g


# ---------------------------------------------------------------------------
# Test classes for each dimension
# ---------------------------------------------------------------------------

class TestSecretsDetection:
    """Tests for dimension 1: secrets detection."""

    def test_secrets_total_count(self):
        model = _make_model_with_secrets()
        result = SecurityService.audit(model)
        assert result['secrets']['total'] == 3

    def test_secrets_by_type(self):
        model = _make_model_with_secrets()
        result = SecurityService.audit(model)
        by_type = result['secrets']['by_type']
        assert by_type.get('Hex High Entropy String') == 2
        assert by_type.get('unknown') == 1

    def test_secrets_top_repos(self):
        model = _make_model_with_secrets()
        result = SecurityService.audit(model)
        top_repos = result['secrets']['top_repos']
        assert len(top_repos) >= 2
        # First entry should be repo-a with 2 secrets
        assert top_repos[0]['count'] == 2
        assert 'repo-a' in top_repos[0]['repo']

    def test_secrets_in_dimensions_found(self):
        model = _make_model_with_secrets()
        result = SecurityService.audit(model)
        assert 'secrets' in result['summary']['dimensions_found']

    def test_empty_model_no_secrets(self):
        model = _make_empty_model()
        result = SecurityService.audit(model)
        assert result['secrets']['total'] == 0
        assert result['secrets']['by_type'] == {}
        assert result['secrets']['top_repos'] == []


class TestVulnerabilityDetection:
    """Tests for dimension 2: vulnerability detection."""

    def test_vulns_total_count(self):
        model = _make_model_with_vulnerabilities()
        result = SecurityService.audit(model)
        assert result['vulnerabilities']['total'] == 3

    def test_vulns_by_severity(self):
        model = _make_model_with_vulnerabilities()
        result = SecurityService.audit(model)
        sev = result['vulnerabilities']['by_severity']
        assert sev.get('critical') == 1
        assert sev.get('high') == 1
        assert sev.get('moderate') == 1

    def test_vulns_in_dimensions_found(self):
        model = _make_model_with_vulnerabilities()
        result = SecurityService.audit(model)
        assert 'vulnerabilities' in result['summary']['dimensions_found']

    def test_empty_model_no_vulns(self):
        model = _make_empty_model()
        result = SecurityService.audit(model)
        assert result['vulnerabilities']['total'] == 0
        assert result['vulnerabilities']['by_severity'] == {}


class TestOutdatedDetection:
    """Tests for dimension 3: outdated dependencies detection."""

    def test_outdated_eol_count(self):
        model = _make_model_with_outdated()
        result = SecurityService.audit(model)
        assert result['outdated']['total_eol'] == 1

    def test_outdated_approaching_count(self):
        model = _make_model_with_outdated()
        result = SecurityService.audit(model)
        assert result['outdated']['total_approaching_eol'] == 1

    def test_outdated_items_platform(self):
        model = _make_model_with_outdated()
        result = SecurityService.audit(model)
        items = result['outdated']['items']
        assert len(items) == 2
        # Both should have platform='Python' (after External/)
        for item in items:
            assert item['platform'] == 'Python'

    def test_frameworks_deprecated(self):
        model = _make_model_with_outdated()
        result = SecurityService.audit(model)
        fd = result['outdated']['frameworks_deprecated']
        assert len(fd) == 1
        assert 'jQuery' in fd[0]['description']

    def test_outdated_in_dimensions_found(self):
        model = _make_model_with_outdated()
        result = SecurityService.audit(model)
        assert 'outdated' in result['summary']['dimensions_found']

    def test_empty_model_no_outdated(self):
        model = _make_empty_model()
        result = SecurityService.audit(model)
        assert result['outdated']['total_eol'] == 0
        assert result['outdated']['total_approaching_eol'] == 0
        assert result['outdated']['items'] == []
        assert result['outdated']['frameworks_deprecated'] == []


class TestRiskDetection:
    """Tests for dimension 4: risk metrics detection."""

    def test_small_dir_excluded(self):
        """Dirs with loc < 100 should be filtered out."""
        model = _make_model_with_risk()
        result = SecurityService.audit(model)
        risk_paths = [r['path'] for r in result['risk']['high_risk_repos']]
        assert not any('tiny' in p for p in risk_paths)

    def test_risk_sorted_by_density(self):
        """Results should be sorted by risk_density descending."""
        model = _make_model_with_risk()
        result = SecurityService.audit(model)
        items = result['risk']['high_risk_repos']
        assert len(items) == 2
        # big_dir has rd=300, repo has rd=250.5
        assert items[0]['risk_density'] == 300.0
        assert items[1]['risk_density'] == 250.5

    def test_avg_softagram_index(self):
        """Average SI of repo(35) and big_dir(28) = 31.5."""
        model = _make_model_with_risk()
        result = SecurityService.audit(model)
        assert result['risk']['avg_softagram_index'] == 31.5

    def test_si_distribution(self):
        """Both SI values (35, 28) fall in 25-50 bucket."""
        model = _make_model_with_risk()
        result = SecurityService.audit(model)
        dist = result['risk']['distribution']
        assert dist['25-50'] == 2
        assert dist['0-25'] == 0
        assert dist['50-75'] == 0
        assert dist['75-100'] == 0

    def test_risk_in_dimensions_found(self):
        model = _make_model_with_risk()
        result = SecurityService.audit(model)
        assert 'risk' in result['summary']['dimensions_found']

    def test_empty_model_no_risk(self):
        model = _make_empty_model()
        result = SecurityService.audit(model)
        assert result['risk']['high_risk_repos'] == []
        assert result['risk']['avg_softagram_index'] == 0.0


class TestBackstageDetection:
    """Tests for dimension 5: backstage metadata detection."""

    def test_backstage_services_count(self):
        model = _make_model_with_backstage()
        result = SecurityService.audit(model)
        assert result['backstage']['services_found'] == 3

    def test_backstage_lifecycle_counts(self):
        model = _make_model_with_backstage()
        result = SecurityService.audit(model)
        lc = result['backstage']['by_lifecycle']
        assert lc.get('production') == 2
        assert lc.get('deprecated') == 1

    def test_backstage_exposed_services(self):
        model = _make_model_with_backstage()
        result = SecurityService.audit(model)
        exposed = result['backstage']['exposed_to_public']
        assert len(exposed) == 1
        assert 'service-a' in exposed

    def test_backstage_owner_counts(self):
        model = _make_model_with_backstage()
        result = SecurityService.audit(model)
        owners = result['backstage']['owners']
        assert owners.get('team-alpha') == 2
        assert owners.get('team-beta') == 1

    def test_backstage_in_dimensions_found(self):
        model = _make_model_with_backstage()
        result = SecurityService.audit(model)
        assert 'backstage' in result['summary']['dimensions_found']

    def test_empty_model_no_backstage(self):
        model = _make_empty_model()
        result = SecurityService.audit(model)
        assert result['backstage']['services_found'] == 0
        assert result['backstage']['by_lifecycle'] == {}
        assert result['backstage']['exposed_to_public'] == []
        assert result['backstage']['owners'] == {}


class TestBusFactorDetection:
    """Tests for dimension 6: bus factor / knowledge concentration detection."""

    def test_single_author_files_only_large(self):
        """Only files with loc > 500 and author_count <= 1 are flagged."""
        model = _make_model_with_bus_factor()
        result = SecurityService.audit(model)
        saf = result['bus_factor']['single_author_files']
        assert len(saf) == 1
        assert 'critical.py' in saf[0]['path']
        assert saf[0]['loc'] == 3000

    def test_low_author_repos_avg(self):
        """Weighted average author count: (1*3000 + 1*50 + 5*2000) / 5050 ~ 2.58."""
        model = _make_model_with_bus_factor()
        result = SecurityService.audit(model)
        repos = result['bus_factor']['low_author_repos']
        assert len(repos) == 1
        assert repos[0]['avg_author_count'] == pytest.approx(2.58, abs=0.01)

    def test_bus_factor_in_dimensions_found(self):
        model = _make_model_with_bus_factor()
        result = SecurityService.audit(model)
        assert 'bus_factor' in result['summary']['dimensions_found']

    def test_empty_model_no_bus_factor(self):
        model = _make_empty_model()
        result = SecurityService.audit(model)
        assert result['bus_factor']['single_author_files'] == []
        assert result['bus_factor']['low_author_repos'] == []


class TestScopePath:
    """Tests for the scope_path parameter."""

    def test_invalid_scope_returns_error(self):
        model = _make_empty_model()
        result = SecurityService.audit(model, scope_path='/nonexistent')
        assert 'error' in result

    def test_scoped_audit_limits_traversal(self):
        """When scoping to repo-a, secrets from repo-b should not appear."""
        model = _make_model_with_secrets()
        result = SecurityService.audit(model, scope_path='/Project/repo-a')
        assert result['secrets']['total'] == 2


class TestTopN:
    """Tests for top_n limiting."""

    def test_top_n_limits_secrets_repos(self):
        g = SGraph()
        for i in range(20):
            repo = g.createOrGetElementFromPath(f'/Project/repo-{i:02d}')
            repo.setType('repository')
            s = g.createOrGetElementFromPath(f'/Project/repo-{i:02d}/f.py/potential_secret x{i}')
            s.setType('potential_secret')
            s.addAttribute('secret_type', 'test')

        result = SecurityService.audit(g, top_n=5)
        assert len(result['secrets']['top_repos']) == 5

    def test_top_n_limits_risk_items(self):
        g = SGraph()
        for i in range(15):
            d = g.createOrGetElementFromPath(f'/Project/repo/dir-{i:02d}')
            d.setType('dir')
            d.addAttribute('loc', '1000')
            d.addAttribute('risk_density', str(float(i * 10)))
            d.addAttribute('softagram_index', str(50))

        result = SecurityService.audit(g, top_n=5)
        assert len(result['risk']['high_risk_repos']) == 5


class TestSummary:
    """Tests for the summary section."""

    def test_repo_and_file_counts(self):
        model = _make_empty_model()
        result = SecurityService.audit(model)
        assert result['summary']['total_repositories'] == 1
        assert result['summary']['total_files'] == 1

    def test_empty_dimensions_found(self):
        model = _make_empty_model()
        result = SecurityService.audit(model)
        assert result['summary']['dimensions_found'] == []


if __name__ == "__main__":
    pytest.main([__file__])
