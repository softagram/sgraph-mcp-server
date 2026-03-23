"""
Security audit service for sgraph models.

Traverses a model and collects security-relevant data across 6 dimensions:
1. Secrets - potential secrets detected in code
2. Vulnerabilities - known CVEs in dependencies
3. Outdated - end-of-life or approaching-EOL dependencies
4. Risk - code quality risk metrics (risk density, softagram index)
5. Backstage - service catalog metadata (lifecycle, ownership, exposure)
6. Bus factor - knowledge concentration (single-author files, low author diversity)
"""

import logging
from collections import Counter, defaultdict
from typing import Any, Dict, Optional

from sgraph import SGraph, SElement

logger = logging.getLogger(__name__)


def _safe_int(value: str, default: int = 0) -> int:
    """Safely convert a string attribute value to int."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _safe_float(value: str, default: float = 0.0) -> float:
    """Safely convert a string attribute value to float."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _get_repo_path(element: SElement) -> str:
    """Get the repository path for an element by walking up to the nearest repository ancestor."""
    ancestor = element.getAncestorOfType('repository')
    return ancestor.getPath() if ancestor else 'unknown'


# File extensions excluded from bus factor analysis (data/config, not source code)
_NON_CODE_EXTENSIONS = frozenset({
    'xml', 'json', 'yaml', 'yml', 'csv', 'tsv', 'txt', 'md', 'rst',
    'html', 'htm', 'css', 'svg', 'png', 'jpg', 'jpeg', 'gif', 'ico',
    'woff', 'woff2', 'ttf', 'eot', 'map', 'lock', 'toml', 'ini', 'cfg',
    'conf', 'properties', 'env',
})


def _is_code_file(element: SElement) -> bool:
    """Check if a file element represents source code (not data/config)."""
    name = element.name
    dot_pos = name.rfind('.')
    if dot_pos == -1:
        return True  # no extension — treat as code
    ext = name[dot_pos + 1:].lower()
    return ext not in _NON_CODE_EXTENSIONS


class SecurityService:
    """Provides security audit functionality across 6 dimensions."""

    @staticmethod
    def audit(model: SGraph, scope_path: Optional[str] = None, top_n: int = 10) -> Dict[str, Any]:
        """Run a security audit on the model, returning data for all 6 dimensions.

        Args:
            model: The sgraph model to audit.
            scope_path: Optional path to limit the audit scope.
            top_n: Maximum number of items in top-N lists.

        Returns:
            Dictionary with summary and per-dimension results.
        """
        logger.debug(f"Starting security audit: scope='{scope_path}', top_n={top_n}")

        # Determine root element
        if scope_path:
            root = model.findElementFromPath(scope_path)
            if root is None:
                return {"error": f"Scope path not found: {scope_path}"}
        else:
            root = model.rootNode

        # --- Accumulators ---

        repo_count = 0
        file_count = 0

        # Dim 1: Secrets
        secrets_total = 0
        secrets_by_type = Counter()
        secrets_by_repo = Counter()

        # Dim 2: Vulnerabilities
        vulns_total = 0
        vulns_by_severity = Counter()

        # Dim 3: Outdated
        outdated_eol = 0
        outdated_approaching = 0
        outdated_items = []
        frameworks_deprecated = []

        # Dim 4: Risk
        risk_items = []
        softagram_indices = []

        # Dim 5: Backstage
        backstage_services = 0
        backstage_lifecycle = Counter()
        backstage_exposed = []
        backstage_owners = Counter()

        # Dim 6: Bus factor
        single_author_files = []
        repo_author_data = defaultdict(lambda: {'total_loc': 0, 'weighted_authors': 0})

        # --- Iterative traversal ---

        stack = [root]
        while stack:
            elem = stack.pop()
            elem_type = elem.getType()

            if elem_type == 'repository':
                repo_count += 1
            elif elem_type == 'file':
                file_count += 1

            # Dim 1: Secrets
            if elem_type == 'potential_secret':
                secrets_total += 1
                secret_type = elem.attrs.get('secret_type') or 'unknown'
                secrets_by_type[secret_type] += 1
                secrets_by_repo[_get_repo_path(elem)] += 1

            # Dim 2: Vulnerabilities
            if elem_type == 'vulnerability':
                vulns_total += 1
                severity = elem.attrs.get('severity', 'unknown')
                vulns_by_severity[severity] += 1

            # Dim 3: Outdated
            outdated_val = elem.attrs.get('outdated')
            if outdated_val:
                if outdated_val == 'fully':
                    outdated_eol += 1
                elif outdated_val == 'almost':
                    outdated_approaching += 1
                # Determine platform from path: .../External/<platform>/...
                path_parts = elem.getPath().split('/')
                platform = 'unknown'
                for i, part in enumerate(path_parts):
                    if part == 'External' and i + 1 < len(path_parts):
                        platform = path_parts[i + 1]
                        break
                outdated_items.append({
                    'path': elem.getPath(),
                    'platform': platform,
                    'outdated': outdated_val,
                    'end_of_life': elem.attrs.get('end_of_life', ''),
                })

            if elem_type == 'framework_deprecation':
                frameworks_deprecated.append({
                    'path': elem.getPath(),
                    'description': elem.attrs.get('description', ''),
                })

            # Dim 4: Risk
            if (elem.typeEquals('dir') or elem.typeEquals('repository')) and 'risk_density' in elem.attrs:
                loc = _safe_int(elem.attrs.get('loc', '0'))
                if loc > 100:
                    rd = _safe_float(elem.attrs.get('risk_density', '0'))
                    si = _safe_int(elem.attrs.get('softagram_index', '0'))
                    am = _safe_int(elem.attrs.get('architecture_modularity', '0'))
                    risk_items.append({
                        'path': elem.getPath(),
                        'risk_density': rd,
                        'softagram_index': si,
                        'architecture_modularity': am,
                        'loc': loc,
                    })
                    if 'softagram_index' in elem.attrs:
                        softagram_indices.append(si)

            # Dim 5: Backstage
            has_backstage = any(k.startswith('backstage__') for k in elem.attrs)
            if has_backstage:
                owner = elem.attrs.get('backstage__spec__owner')
                lifecycle = elem.attrs.get('backstage__spec__lifecycle')
                exposed = elem.attrs.get('backstage__metadata__tags__exposed_to_public')
                if owner or lifecycle:
                    backstage_services += 1
                    if owner:
                        backstage_owners[owner] += 1
                    if lifecycle:
                        backstage_lifecycle[lifecycle] += 1
                    if exposed == 'true':
                        backstage_exposed.append(elem.name)

            # Dim 6: Bus factor (code files only, skip data/config)
            if elem_type == 'file' and 'author_count_365' in elem.attrs and _is_code_file(elem):
                ac = _safe_int(elem.attrs.get('author_count_365', '0'))
                loc = _safe_int(elem.attrs.get('loc', '0'))
                if ac <= 1 and loc > 500:
                    single_author_files.append({
                        'path': elem.getPath(),
                        'loc': loc,
                        'author_count_365': ac,
                    })
                if loc > 0:
                    repo_path = _get_repo_path(elem)
                    repo_author_data[repo_path]['total_loc'] += loc
                    repo_author_data[repo_path]['weighted_authors'] += ac * loc

            stack.extend(elem.children)

        # --- Post-processing ---

        dimensions_found = []

        if secrets_total > 0:
            dimensions_found.append('secrets')
        if vulns_total > 0:
            dimensions_found.append('vulnerabilities')
        if outdated_eol > 0 or outdated_approaching > 0 or frameworks_deprecated:
            dimensions_found.append('outdated')

        # Risk: sort by density descending, compute SI stats
        risk_items.sort(key=lambda x: x['risk_density'], reverse=True)
        avg_si = sum(softagram_indices) / len(softagram_indices) if softagram_indices else 0.0
        distribution = {'0-25': 0, '25-50': 0, '50-75': 0, '75-100': 0}
        for si in softagram_indices:
            if si < 25:
                distribution['0-25'] += 1
            elif si < 50:
                distribution['25-50'] += 1
            elif si < 75:
                distribution['50-75'] += 1
            else:
                distribution['75-100'] += 1
        if risk_items:
            dimensions_found.append('risk')

        if backstage_services > 0:
            dimensions_found.append('backstage')

        # Bus factor: sort single-author files by LOC descending
        single_author_files.sort(key=lambda x: x['loc'], reverse=True)
        low_author_repos = []
        for repo_path, data in repo_author_data.items():
            if data['total_loc'] > 0:
                avg_ac = data['weighted_authors'] / data['total_loc']
                low_author_repos.append({
                    'path': repo_path,
                    'total_loc': data['total_loc'],
                    'avg_author_count': round(avg_ac, 2),
                })
        low_author_repos.sort(key=lambda x: x['avg_author_count'])
        if single_author_files or low_author_repos:
            dimensions_found.append('bus_factor')

        logger.debug(
            f"Security audit complete: {repo_count} repos, {file_count} files, "
            f"dimensions found: {dimensions_found}"
        )

        return {
            'summary': {
                'total_repositories': repo_count,
                'total_files': file_count,
                'dimensions_found': dimensions_found,
            },
            'secrets': {
                'total': secrets_total,
                'by_type': dict(secrets_by_type),
                'top_repos': sorted(
                    [{'repo': r, 'count': c} for r, c in secrets_by_repo.items()],
                    key=lambda x: x['count'], reverse=True,
                )[:top_n],
            },
            'vulnerabilities': {
                'total': vulns_total,
                'by_severity': dict(vulns_by_severity),
                'top_repos': [],
            },
            'outdated': {
                'total_eol': outdated_eol,
                'total_approaching_eol': outdated_approaching,
                'items': outdated_items[:top_n],
                'frameworks_deprecated': frameworks_deprecated[:top_n],
            },
            'risk': {
                'high_risk_repos': risk_items[:top_n],
                'avg_softagram_index': round(avg_si, 1),
                'distribution': distribution,
            },
            'backstage': {
                'services_found': backstage_services,
                'by_lifecycle': dict(backstage_lifecycle),
                'exposed_to_public': backstage_exposed,
                'owners': dict(backstage_owners),
            },
            'bus_factor': {
                'single_author_files': single_author_files[:top_n],
                'low_author_repos': low_author_repos[:top_n],
            },
        }
