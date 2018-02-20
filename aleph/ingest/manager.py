import os
import logging
from tempfile import mkdtemp

from ingestors import Manager
from ingestors.util import decode_path, remove_directory

from aleph.core import db, settings
from aleph.model import Document, Cache
from aleph.ingest.result import DocumentResult

log = logging.getLogger(__name__)


class DocumentManager(Manager):
    """Handle the process of ingesting documents.

    This includes creating and flushing records, setting document state and
    dispatching child ingestors as needed.
    """

    RESULT_CLASS = DocumentResult

    def __init__(self, archive):
        super(DocumentManager, self).__init__({
            'PDF_OCR_PAGES': True,
            'OCR_DEFAULTS': settings.OCR_DEFAULTS
        })
        self.archive = archive

    def before(self, result):
        db.session.flush()
        result.document.status = Document.STATUS_PENDING
        result.document.delete_records()

    def after(self, result):
        from aleph.logic.documents import process_document
        result.update()
        db.session.commit()
        document = result.document
        log.debug('Ingested [%s:%s]: %s',
                  document.id, document.schema, document.title)
        process_document(document)

    def get_cache(self, key):
        return Cache.get_cache(key)

    def set_cache(self, key, value):
        Cache.set_cache(key, value)

    def handle_child(self, parent, file_path, title=None, mime_type=None,
                     id=None, file_name=None):
        file_path = decode_path(file_path)
        assert id is not None, (parent, file_path)

        doc = Document.by_keys(parent_id=parent.document.id,
                               collection=parent.document.collection,
                               foreign_id=id)
        doc.title = title or doc.meta.get('title')
        doc.file_name = file_name or doc.meta.get('file_name')
        doc.mime_type = mime_type or doc.meta.get('mime_type')

        from aleph.ingest import ingest_document
        ingest_document(doc, file_path, role_id=parent.role_id)
        return DocumentResult(self, doc,
                              file_path=file_path,
                              role_id=parent.role_id)

    def ingest_document(self, document, file_path=None,
                        role_id=None, shallow=False):
        """Ingest a database-backed document.

        First retrieve its data and then call the actual ingestor.
        """
        # Work path will be used by storagelayer to cache a local
        # copy of data from an S3-based archive, and by ingestors
        # to perform processing and generate intermediary files.
        work_path = mkdtemp(prefix="aleph.ingest.")
        content_hash = document.content_hash
        if file_path is None and content_hash is not None:
            file_name = document.safe_file_name
            file_path = self.archive.load_file(content_hash,
                                               file_name=file_name,
                                               temp_path=work_path)

        if file_path is not None and not os.path.exists(file_path):
            # Probably indicative of file system encoding issues.
            log.error("Invalid path [%r]: %s", document, file_path)
            return

        try:
            if not len(document.languages):
                document.languages = document.collection.languages

            if not len(document.countries):
                document.countries = document.collection.countries

            result = DocumentResult(self, document,
                                    file_path=file_path,
                                    role_id=role_id)
            self.ingest(file_path, result=result)

            if not shallow and file_path is None:
                # When a directory is ingested, the data is not stored. Thus,
                # try to recurse on the database-backed known children.
                for child in Document.by_parent(document):
                    from aleph.ingest import ingest_document
                    ingest_document(child, None, role_id=role_id)
        finally:
            db.session.rollback()
            # Removing the temp_path given to storagelayer makes it redundant
            # to also call cleanup on the archive.
            remove_directory(work_path)
