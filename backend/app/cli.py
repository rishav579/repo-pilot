"""
RepoPilot Developer CLI — Minimal command-line interface for local repository workflow.

USAGE:
    python -m app.cli register <path>
    python -m app.cli index <repository_id>
    python -m app.cli status <repository_id>
    python -m app.cli query <repository_id> "<question>"
"""

import sys
from app.services.rag.engine import RAGService
from app.services.rag.models import RAGRequest
from app.services.repository.service import RepositoryService


def print_help():
    print("RepoPilot Developer CLI")
    print("Commands:")
    print("  python -m app.cli register <path>")
    print("  python -m app.cli index <repository_id>")
    print("  python -m app.cli status <repository_id>")
    print("  python -m app.cli query <repository_id> \"<question>\"")


def main():
    if len(sys.argv) < 2:
        print_help()
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == "register":
        if len(sys.argv) < 3:
            print("Error: Path required. Usage: python -m app.cli register <path>")
            sys.exit(1)
        path = sys.argv[2]
        srv = RepositoryService()
        try:
            record = srv.register_repository(path)
            print(f"Registered repository ID: {record.repository_id}")
            print(f"Display Name: {record.display_name}")
            print(f"Canonical Path: {record.canonical_path}")
            print(f"Status: {record.status.value}")
        finally:
            srv.close()

    elif cmd == "index":
        if len(sys.argv) < 3:
            print("Error: Repository ID required. Usage: python -m app.cli index <repository_id>")
            sys.exit(1)
        repo_id = sys.argv[2]
        srv = RepositoryService()
        try:
            summary = srv.index_repository(repo_id)
            print(f"Indexing completed for {repo_id}:")
            print(f"Status: {summary.status.value}")
            print(f"Files Discovered: {summary.files_discovered}")
            print(f"Files Parsed: {summary.files_parsed}")
            print(f"Chunks Created/Updated: {summary.chunks_created}/{summary.chunks_updated}")
            print(f"Duration: {summary.duration_ms} ms")
        finally:
            srv.close()

    elif cmd == "status":
        if len(sys.argv) < 3:
            print("Error: Repository ID required. Usage: python -m app.cli status <repository_id>")
            sys.exit(1)
        repo_id = sys.argv[2]
        srv = RepositoryService()
        try:
            record = srv.get_repository(repo_id)
            if not record:
                print(f"Error: Repository '{repo_id}' not found.")
                sys.exit(1)
            print(f"Repository ID: {record.repository_id}")
            print(f"Status: {record.status.value}")
            print(f"Indexed Files: {record.indexed_file_count}")
            print(f"Indexed Chunks: {record.indexed_chunk_count}")
            print(f"Last Indexed At: {record.last_indexed_at}")
        finally:
            srv.close()

    elif cmd == "query":
        if len(sys.argv) < 4:
            print("Error: Repository ID and question required. Usage: python -m app.cli query <repo_id> \"question\"")
            sys.exit(1)
        repo_id = sys.argv[2]
        question = sys.argv[3]

        rag = RAGService()
        try:
            req = RAGRequest(repository_path=repo_id, question=question, mode="auto")
            resp = rag.query(req)
            print(f"Question: {resp.question}")
            print(f"Status: {resp.status}")
            print(f"Answer: {resp.answer}")
            if resp.citations:
                print("\nCitations:")
                for c in resp.citations:
                    print(f"  [{c.index_number}] {c.relative_path} (L{c.start_line}-L{c.end_line})")
        finally:
            rag.close()

    else:
        print(f"Unknown command '{cmd}'.")
        print_help()


if __name__ == "__main__":
    main()
