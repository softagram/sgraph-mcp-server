"""
CLI tool for generating security audit reports from sgraph models.

Usage:
    uv run python -m src.tools.security_report_cli /path/to/model.xml.zip
    uv run python -m src.tools.security_report_cli /path/to/model.xml.zip -o report.md
    uv run python -m src.tools.security_report_cli /path/to/model.xml.zip --scope "/Project/Group" --top-n 20
"""

import argparse
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from sgraph.loader.modelloader import ModelLoader
from src.services.security_service import SecurityService


def format_markdown(result: dict, model_path: str, scope: str | None) -> str:
    """Format audit result as markdown."""
    lines = []
    lines.append('# Security Audit Report')
    lines.append(f'**Model:** {model_path}')
    lines.append(f'**Date:** {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    lines.append(f'**Scope:** {scope or "(all)"}')
    lines.append('')

    s = result['summary']
    lines.append('## Summary')
    lines.append(f'- **Repositories:** {s["total_repositories"]}')
    lines.append(f'- **Files:** {s["total_files"]}')
    lines.append(f'- **Dimensions with findings:** {", ".join(s["dimensions_found"]) or "none"}')
    lines.append('')

    # Secrets
    sec = result['secrets']
    lines.append('## Secrets')
    if sec['total'] == 0:
        lines.append('_No potential secrets found._')
    else:
        lines.append(f'{sec["total"]} potential secrets found.')
        lines.append('')
        if sec['by_type']:
            lines.append('| Type | Count |')
            lines.append('|------|-------|')
            for t, c in sorted(sec['by_type'].items(), key=lambda x: x[1], reverse=True):
                lines.append(f'| {t} | {c} |')
            lines.append('')
        if sec['top_repos']:
            lines.append('### Top Repositories')
            lines.append('| Repository | Count |')
            lines.append('|------------|-------|')
            for r in sec['top_repos']:
                lines.append(f'| {r["repo"]} | {r["count"]} |')
            lines.append('')

    # Vulnerabilities
    vuln = result['vulnerabilities']
    lines.append('## Vulnerabilities')
    if vuln['total'] == 0:
        lines.append('_No vulnerabilities found._')
    else:
        lines.append(f'{vuln["total"]} vulnerabilities found.')
        lines.append('')
        lines.append('| Severity | Count |')
        lines.append('|----------|-------|')
        for sev in ['critical', 'high', 'moderate', 'low']:
            count = vuln['by_severity'].get(sev, 0)
            if count > 0:
                lines.append(f'| {sev} | {count} |')
        lines.append('')

    # Outdated
    od = result['outdated']
    lines.append('## Outdated / End-of-Life')
    if od['total_eol'] == 0 and od['total_approaching_eol'] == 0 and not od['frameworks_deprecated']:
        lines.append('_No outdated or EOL components found._')
    else:
        lines.append(f'- **End of life:** {od["total_eol"]}')
        lines.append(f'- **Approaching EOL:** {od["total_approaching_eol"]}')
        lines.append(f'- **Deprecated frameworks:** {len(od["frameworks_deprecated"])}')
        lines.append('')
        if od['items']:
            lines.append('| Path | Platform | Status | EOL Date |')
            lines.append('|------|----------|--------|----------|')
            for item in od['items']:
                lines.append(f'| {item["path"]} | {item["platform"]} | {item["outdated"]} | {item["end_of_life"]} |')
            lines.append('')

    # Risk
    risk = result['risk']
    lines.append('## Risk Levels')
    if not risk['high_risk_repos']:
        lines.append('_No risk data found._')
    else:
        lines.append(f'**Average Softagram Index:** {risk["avg_softagram_index"]}')
        lines.append('')
        dist = risk['distribution']
        lines.append('| Index Range | Count |')
        lines.append('|-------------|-------|')
        for bucket in ['0-25', '25-50', '50-75', '75-100']:
            lines.append(f'| {bucket} | {dist.get(bucket, 0)} |')
        lines.append('')
        lines.append('### Highest Risk Density')
        lines.append('| Path | Risk Density | Softagram Index | LOC |')
        lines.append('|------|-------------|-----------------|-----|')
        for r in risk['high_risk_repos']:
            lines.append(f'| {r["path"]} | {r["risk_density"]} | {r["softagram_index"]} | {r["loc"]} |')
        lines.append('')

    # Backstage
    bs = result['backstage']
    lines.append('## Backstage Services')
    if bs['services_found'] == 0:
        lines.append('_No Backstage metadata found._')
    else:
        lines.append(f'{bs["services_found"]} services found.')
        lines.append('')
        if bs['by_lifecycle']:
            lines.append('| Lifecycle | Count |')
            lines.append('|-----------|-------|')
            for lc, c in sorted(bs['by_lifecycle'].items(), key=lambda x: x[1], reverse=True):
                lines.append(f'| {lc} | {c} |')
            lines.append('')
        if bs['exposed_to_public']:
            lines.append(f'### Exposed to Public ({len(bs["exposed_to_public"])})')
            for svc in bs['exposed_to_public']:
                lines.append(f'- {svc}')
            lines.append('')
        if bs['owners']:
            lines.append('### Ownership')
            lines.append('| Owner | Services |')
            lines.append('|-------|----------|')
            for owner, c in sorted(bs['owners'].items(), key=lambda x: x[1], reverse=True):
                lines.append(f'| {owner} | {c} |')
            lines.append('')

    # Bus Factor
    bf = result['bus_factor']
    lines.append('## Bus Factor')
    if not bf['single_author_files'] and not bf['low_author_repos']:
        lines.append('_No bus factor data found._')
    else:
        if bf['single_author_files']:
            lines.append(f'### Single-Author Files (LOC > 500): {len(bf["single_author_files"])}')
            lines.append('| Path | LOC |')
            lines.append('|------|-----|')
            for f in bf['single_author_files']:
                lines.append(f'| {f["path"]} | {f["loc"]} |')
            lines.append('')
        if bf['low_author_repos']:
            lines.append('### Repositories by Average Author Count')
            lines.append('| Repository | Total LOC | Avg Authors |')
            lines.append('|------------|-----------|-------------|')
            for r in bf['low_author_repos']:
                lines.append(f'| {r["path"]} | {r["total_loc"]} | {r["avg_author_count"]} |')
            lines.append('')

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Security audit report from sgraph model')
    parser.add_argument('model_path', help='Path to model.xml.zip')
    parser.add_argument('-o', '--output', help='Output file (default: stdout)')
    parser.add_argument('--scope', help='Limit to subtree path')
    parser.add_argument('--top-n', type=int, default=10, help='Max items per list (default: 10)')
    args = parser.parse_args()

    if not os.path.exists(args.model_path):
        print(f'Error: File not found: {args.model_path}', file=sys.stderr)
        sys.exit(1)

    print(f'Loading model: {args.model_path}', file=sys.stderr)
    ml = ModelLoader()
    model = ml.load_model(args.model_path)
    print(f'Model loaded. Running security audit...', file=sys.stderr)

    result = SecurityService.audit(model, scope_path=args.scope, top_n=args.top_n)

    if 'error' in result:
        print(f'Error: {result["error"]}', file=sys.stderr)
        sys.exit(1)

    markdown = format_markdown(result, args.model_path, args.scope)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(markdown)
        print(f'Report written to {args.output}', file=sys.stderr)
    else:
        print(markdown)


if __name__ == '__main__':
    main()
