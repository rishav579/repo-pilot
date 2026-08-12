"""
Ingestion Configuration — What to include and exclude when scanning a repository.

WHY THIS FILE EXISTS:
    Instead of hardcoding exclusion rules throughout the codebase,
    we define them in ONE place. This makes it easy to:
    - Add new exclusions (e.g., a new dependency manager)
    - See all rules at a glance
    - Test the rules independently
    - Let users override defaults in the future

HOW IT WORKS:
    - EXCLUDED_DIRECTORIES: directory names that are always skipped entirely
    - EXCLUDED_FILES: specific filenames that are always skipped
    - BINARY_EXTENSIONS: file extensions that indicate non-text files
    - LANGUAGE_MAP: maps file extensions to programming language names
    - MAX_FILE_SIZE_BYTES: files larger than this are skipped (protects memory)
"""

# ============================================================
# Directories to skip entirely during scanning.
# These are never part of the developer's actual source code.
# ============================================================
EXCLUDED_DIRECTORIES: set[str] = {
    # Version control
    ".git",
    ".svn",
    ".hg",

    # Python
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",

    # Node.js / JavaScript
    "node_modules",
    ".next",
    ".nuxt",
    "bower_components",

    # Build output
    "dist",
    "build",
    "out",
    "target",       # Java/Rust build output
    "bin",          # Compiled binaries

    # IDE / Editor
    ".idea",
    ".vscode",
    ".vs",

    # OS
    ".DS_Store",    # macOS (also a file, but safe to list here)
    "__MACOSX",

    # Other
    ".cache",
    ".tox",
    "coverage",
    "htmlcov",
    ".terraform",
}

# ============================================================
# Directory suffixes to skip entirely.
# Directories ending with any of these suffixes are excluded.
# ============================================================
EXCLUDED_DIR_SUFFIXES: set[str] = {
    ".egg-info",
    ".dist-info",
}

# ============================================================
# Specific filenames to skip (regardless of directory).
# These are typically auto-generated or not useful for analysis.
# ============================================================
EXCLUDED_FILES: set[str] = {
    # Lock files (auto-generated, extremely large, no logic)
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Pipfile.lock",
    "composer.lock",
    "Gemfile.lock",
    "Cargo.lock",

    # OS files
    ".DS_Store",
    "Thumbs.db",
    "Desktop.ini",

    # Editor files
    ".editorconfig",

    # Other
    ".gitattributes",
}

# ============================================================
# File extensions that indicate binary (non-text) files.
# Binary files cannot be parsed as source code.
# ============================================================
BINARY_EXTENSIONS: set[str] = {
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
    ".webp", ".tiff", ".tif",

    # Fonts
    ".woff", ".woff2", ".ttf", ".otf", ".eot",

    # Audio / Video
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv", ".flac",
    ".ogg", ".webm",

    # Archives
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar", ".xz",

    # Compiled / Executables
    ".exe", ".dll", ".so", ".dylib", ".o", ".a",
    ".pyc", ".pyo", ".pyd", ".class", ".jar", ".war",
    ".whl", ".egg",

    # Documents (binary formats)
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",

    # Databases
    ".sqlite", ".sqlite3", ".db",

    # Other binary
    ".bin", ".dat", ".pkl", ".pickle", ".npy", ".npz",
    ".h5", ".hdf5", ".parquet", ".feather",
}

# ============================================================
# Map file extensions to programming language names.
# Used for reporting which languages are in a repository.
# ============================================================
LANGUAGE_MAP: dict[str, str] = {
    # Python
    ".py": "Python",
    ".pyi": "Python",
    ".pyx": "Python",

    # JavaScript / TypeScript
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",

    # Web
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "Sass",
    ".less": "Less",

    # JVM
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".scala": "Scala",
    ".groovy": "Groovy",

    # Systems
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cxx": "C++",
    ".cc": "C++",
    ".hpp": "C++",
    ".cs": "C#",
    ".rs": "Rust",
    ".go": "Go",
    ".swift": "Swift",

    # Scripting
    ".rb": "Ruby",
    ".php": "PHP",
    ".pl": "Perl",
    ".pm": "Perl",
    ".lua": "Lua",
    ".r": "R",
    ".R": "R",
    ".jl": "Julia",

    # Shell
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".fish": "Shell",
    ".ps1": "PowerShell",
    ".bat": "Batch",
    ".cmd": "Batch",

    # Data / Config
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".xml": "XML",
    ".ini": "INI",
    ".cfg": "INI",
    ".env": "Env",

    # Documentation
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".txt": "Text",

    # Other
    ".sql": "SQL",
    ".graphql": "GraphQL",
    ".proto": "Protobuf",
    ".dockerfile": "Dockerfile",
    ".tf": "Terraform",
    ".hcl": "HCL",
    ".cmake": "CMake",
    ".makefile": "Makefile",
}

# ============================================================
# Maximum file size to process (in bytes).
# Files larger than this are skipped to protect memory.
# 1 MB = 1,048,576 bytes — generous for source code.
# Most source files are under 100 KB.
# ============================================================
MAX_FILE_SIZE_BYTES: int = 1_048_576  # 1 MB
