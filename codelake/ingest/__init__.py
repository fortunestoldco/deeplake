"""
Documentation ingestion module for codelake.
"""

from codelake.ingest.documentation_ingest import ingest_sdk_documentation
from codelake.ingest.updater import DocumentationUpdater, get_updater

# Create alias for backward compatibility
documentation_ingestion = ingest_sdk_documentation