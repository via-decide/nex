"""
Nex - EPUB Pipeline Adapter

This module provides a robust, production-ready pipeline adapter for converting
generated research reports, chapters, and markdown documents into fully structured,
Kindle-compatible EPUB3 files. 

It handles:
- Markdown to HTML conversion (with advanced extensions: tables, footnotes, math).
- Automated chapter ordering and TOC (Table of Contents) generation.
- Rich metadata injection (Dublin Core standards).
- Cover image embedding.
- Kindle-specific optimizations (NCX fallbacks, specific CSS media queries).
- Semantic structural tagging for e-readers.

Dependencies:
    - ebooklib
    - markdown
    - bs4 (BeautifulSoup) - Optional, for advanced HTML cleaning.
"""

import os
import re
import uuid
import logging
import warnings
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Union, Any, Tuple

# Third-party imports
try:
    import markdown
except ImportError:
    warnings.warn("The 'markdown' package is required for EpubPipelineAdapter.")

try:
    from ebooklib import epub
except ImportError:
    warnings.warn("The 'ebooklib' package is required for EpubPipelineAdapter.")

# Configure module logger
logger = logging.getLogger("nex.writing.epub_adapter")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)


# =============================================================================
# Exceptions
# =============================================================================

class EpubAdapterError(Exception):
    """Base exception for all EPUB adapter related errors."""
    pass

class MetadataError(EpubAdapterError):
    """Raised when required metadata is missing or invalid."""
    pass

class MarkdownConversionError(EpubAdapterError):
    """Raised when markdown cannot be parsed or converted."""
    pass

class PipelineExportError(EpubAdapterError):
    """Raised when the final EPUB compilation or export fails."""
    pass


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class BookMetadata:
    """
    Encapsulates all metadata required for a standard EPUB publication.
    Complies with Dublin Core metadata standards used in EPUB3.
    """
    title: str
    author: str
    identifier: str = field(default_factory=lambda: str(uuid.uuid4()))
    language: str = "en"
    description: Optional[str] = None
    publisher: str = "Nex Autonomous Research Agent"
    publication_date: str = field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%d"))
    subjects: List[str] = field(default_factory=list)
    rights: str = "All rights reserved."
    cover_image_path: Optional[Union[str, Path]] = None

    def validate(self) -> None:
        """Validates that essential metadata is present."""
        if not self.title:
            raise MetadataError("Book title cannot be empty.")
        if not self.author:
            raise MetadataError("Book author cannot be empty.")
        if not self.identifier:
            raise MetadataError("Book identifier (UUID/ISBN) cannot be empty.")


@dataclass
class Chapter:
    """
    Represents a single chapter or structural unit within the book.
    """
    id: str
    title: str
    markdown_content: str
    html_content: str = ""
    order: int = 0
    is_frontmatter: bool = False
    epub_item: Optional[Any] = None  # Holds the ebooklib.epub.EpubHtml instance
    file_name: str = ""

    def __post_init__(self):
        if not self.file_name:
            # Generate a safe filename for the EPUB internal structure
            safe_title = re.sub(r'[^a-z0-9]+', '_', self.title.lower()).strip('_')
            prefix = "front_" if self.is_frontmatter else "chap_"
            self.file_name = f"{prefix}{self.order:03d}_{safe_title}.xhtml"


# =============================================================================
# Core Pipeline Adapter
# =============================================================================

class EpubPipelineAdapter:
    """
    Orchestrates the conversion of Markdown documents into a Kindle-ready EPUB.
    
    Features:
        - Ingests raw Markdown or files.
        - Applies standard and Kindle-specific CSS.
        - Generates NCX and NAV elements.
        - Builds structural hierarchy (Spine & TOC).
    """

    # Default CSS optimized for e-readers, specifically Kindle KF8/KFX formats.
    DEFAULT_CSS = """
    @namespace epub "http://www.idpf.org/2007/ops";
    
    body {
        font-family: "Palatino Linotype", "Book Antiqua", Palatino, serif;
        margin: 5%;
        text-align: justify;
        line-height: 1.4;
        color: #000000;
        background-color: #FFFFFF;
    }
    
    h1, h2, h3, h4, h5, h6 {
        font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
        font-weight: bold;
        text-align: left;
        page-break-after: avoid;
        color: #111111;
        margin-top: 1em;
        margin-bottom: 0.5em;
    }
    
    h1 { font-size: 2em; text-align: center; margin-bottom: 1.5em; }
    h2 { font-size: 1.5em; }
    h3 { font-size: 1.25em; }
    
    p {
        margin-top: 0;
        margin-bottom: 0.5em;
        text-indent: 1.5em;
    }
    
    p.no-indent {
        text-indent: 0;
    }
    
    hr {
        border: 0;
        border-bottom: 1px solid #ccc;
        margin: 2em auto;
        width: 50%;
    }
    
    a {
        color: #0000EE;
        text-decoration: underline;
    }
    
    blockquote {
        margin: 1em 2em;
        padding-left: 1em;
        border-left: 2px solid #666;
        font-style: italic;
        color: #333;
    }
    
    ul, ol {
        margin: 1em 0;
        padding-left: 2em;
    }
    
    li {
        margin-bottom: 0.5em;
    }
    
    table {
        width: 100%;
        border-collapse: collapse;
        margin: 1em 0;
    }
    
    th, td {
        border: 1px solid #999;
        padding: 0.5em;
        text-align: left;
    }
    
    th {
        background-color: #f2f2f2;
    }
    
    img {
        max-width: 100%;
        height: auto;
        display: block;
        margin: 1em auto;
    }
    
    /* Kindle specific optimizations */
    @media amzn-kf8 {
        p {
            text-indent: 5%;
        }
    }
    
    .chapter-title {
        page-break-before: always;
    }
    
    .footnote {
        font-size: 0.8em;
        vertical-align: super;
    }
    """

    def __init__(self, metadata: BookMetadata):
        """
        Initializes the EPUB pipeline adapter.
        
        Args:
            metadata (BookMetadata): The configuration and metadata for the book.
        """
        logger.info(f"Initializing EpubPipelineAdapter for book: '{metadata.title}'")
        self.metadata = metadata
        self.metadata.validate()
        
        self.book = epub.EpubBook()
        self.chapters: List[Chapter] = []
        self.css_item: Optional[epub.EpubItem] = None
        
        # Initialize markdown converter with extensive plugins suitable for research reports
        self.md_converter = markdown.Markdown(
            extensions=[
                'meta',
                'tables',
                'footnotes',
                'fenced_code',
                'sane_lists',
                'toc',
                'nl2br',
                'attr_list',
                'def_list'
            ]
        )
        
        self._setup_book_metadata()
        self._inject_default_css()

    def _setup_book_metadata(self) -> None:
        """Applies Dublin Core metadata to the ebooklib EpubBook object."""
        logger.debug("Applying Dublin Core metadata to EPUB structure.")
        self.book.set_identifier(self.metadata.identifier)
        self.book.set_title(self.metadata.title)
        self.book.set_language(self.metadata.language)
        self.book.add_author(self.metadata.author)
        
        if self.metadata.description:
            self.book.add_metadata('DC', 'description', self.metadata.description)
        if self.metadata.publisher:
            self.book.add_metadata('DC', 'publisher', self.metadata.publisher)
        if self.metadata.publication_date:
            self.book.add_metadata('DC', 'date', self.metadata.publication_date)
        if self.metadata.rights:
            self.book.add_metadata('DC', 'rights', self.metadata.rights)
            
        for subject in self.metadata.subjects:
            self.book.add_metadata('DC', 'subject', subject)
            
        # Handle cover image if provided
        if self.metadata.cover_image_path:
            self.set_cover_image(self.metadata.cover_image_path)

    def _inject_default_css(self) -> None:
        """Injects the default, Kindle-optimized CSS into the EPUB."""
        logger.debug("Injecting default CSS stylesheet.")
        self.css_item = epub.EpubItem(
            uid="style_nav",
            file_name="style/nav.css",
            media_type="text/css",
            content=self.DEFAULT_CSS
        )
        self.book.add_item(self.css_item)

    def set_cover_image(self, image_path: Union[str, Path]) -> None:
        """
        Embeds a cover image into the EPUB.
        
        Args:
            image_path (Union[str, Path]): File system path to the cover image.
        """
        path = Path(image_path)
        if not path.exists():
            logger.error(f"Cover image not found at path: {path}")
            raise MetadataError(f"Cover image missing: {path}")
            
        logger.info(f"Setting cover image from {path}")
        try:
            with open(path, 'rb') as f:
                cover_content = f.read()
            
            # Determine extension for media type
            ext = path.suffix.lower()
            media_type = "image/jpeg"
            if ext == ".png":
                media_type = "image/png"
            elif ext in [".gif"]:
                media_type = "image/gif"
                
            self.book.set_cover("cover.jpg", cover_content)
        except Exception as e:
            logger.error(f"Failed to set cover image: {str(e)}")
            raise PipelineExportError(f"Cover image processing failed: {e}")

    def add_custom_css(self, css_content: str, file_name: str = "style/custom.css") -> None:
        """
        Allows injection of custom CSS strings for advanced styling pipelines.
        
        Args:
            css_content (str): The raw CSS string.
            file_name (str): The internal EPUB path for the CSS file.
        """
        logger.info(f"Adding custom CSS file: {file_name}")
        custom_css = epub.EpubItem(
            uid=f"custom_css_{uuid.uuid4().hex[:6]}",
            file_name=file_name,
            media_type="text/css",
            content=css_content
        )
        self.book.add_item(custom_css)
        # We also need to ensure existing chapters link to this new CSS
        for chap in self.chapters:
            if chap.epub_item:
                chap.epub_item.add_item(custom_css)

    def convert_markdown_to_html(self, markdown_text: str) -> str:
        """
        Converts raw markdown to HTML, wrapping it in EPUB-friendly tags.
        
        Args:
            markdown_text (str): The markdown string.
            
        Returns:
            str: The converted HTML string.
        """
        try:
            # Reset the converter to clear previous state (like footnotes)
            self.md_converter.reset()
            html_body = self.md_converter.convert(markdown_text)
            
            # Wrap in a clean div structure
            wrapped_html = f"""
            <div class="nex-chapter-content">
                {html_body}
            </div>
            """
            return wrapped_html
        except Exception as e:
            logger.error(f"Markdown conversion failed: {str(e)}")
            raise MarkdownConversionError(f"Failed to convert markdown: {e}")

    def add_chapter(self, title: str, markdown_content: str, is_frontmatter: bool = False) -> Chapter:
        """
        Ingests a markdown string, converts it to an EPUB chapter, and appends it
        to the internal reading order.
        
        Args:
            title (str): Title of the chapter.
            markdown_content (str): The raw markdown text.
            is_frontmatter (bool): If True, chapter is excluded from main numbering (e.g., Preface).
            
        Returns:
            Chapter: The generated Chapter object.
        """
        logger.info(f"Adding chapter: '{title}' (Frontmatter: {is_frontmatter})")
        
        order = len(self.chapters) + 1
        chapter_id = f"chapter_{order:03d}_{uuid.uuid4().hex[:6]}"
        
        html_content = self.convert_markdown_to_html(markdown_content)
        
        # Add a heading to the HTML if the markdown doesn't already have an H1
        if not re.search(r'<h1.*?>', html_content, re.IGNORECASE):
            html_content = f'<h1 class="chapter-title">{title}</h1>\n{html_content}'
            
        chapter = Chapter(
            id=chapter_id,
            title=title,
            markdown_content=markdown_content,
            html_content=html_content,
            order=order,
            is_frontmatter=is_frontmatter
        )
        
        # Create ebooklib EpubHtml item
        epub_chapter = epub.EpubHtml(
            title=title,
            file_name=chapter.file_name,
            lang=self.metadata.language
        )
        
        # Assign semantic types for Kindle/e-reader compatibility
        if is_frontmatter:
            epub_chapter.set_content(html_content)
            # Try to guess semantic type based on title
            lower_title = title.lower()
            if 'copyright' in lower_title:
                epub_chapter.add_item(epub.EpubItem(uid="copyright", file_name="copyright.xhtml"))
                epub_chapter.properties.append('copyright-page')
            elif 'preface' in lower_title or 'introduction' in lower_title:
                epub_chapter.properties.append('preface')
        else:
            epub_chapter.set_content(html_content)
            epub_chapter.properties.append('chapter')

        # Link CSS
        if self.css_item:
            epub_chapter.add_item(self.css_item)
            
        chapter.epub_item = epub_chapter
        
        # Add to book and internal list
        self.book.add_item(epub_chapter)
        self.chapters.append(chapter)
        
        return chapter

    def add_chapter_from_file(self, file_path: Union[str, Path], title: Optional[str] = None, is_frontmatter: bool = False) -> Chapter:
        """
        Reads a markdown file from disk and adds it as a chapter.
        
        Args:
            file_path (Union[str, Path]): Path to the markdown file.
            title (Optional[str]): Title of the chapter. Defaults to filename without extension.
            is_frontmatter (bool): Whether the file is frontmatter.
            
        Returns:
            Chapter: The generated Chapter object.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Markdown file not found: {path}")
            
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if not title:
            # Try to extract title from first H1
            match = re.search(r'^#\s+(.*)', content, re.MULTILINE)
            if match:
                title = match.group(1).strip()
            else:
                title = path.stem.replace('_', ' ').replace('-', ' ').title()
                
        return self.add_chapter(title=title, markdown_content=content, is_frontmatter=is_frontmatter)

    def generate_title_page(self) -> None:
        """
        Auto-generates a semantic title page based on BookMetadata and inserts it
        as the very first frontmatter item.
        """
        logger.info("Generating standard title page.")
        
        title_html = f"""
        <div style="text-align: center; margin-top: 20%;">
            <h1 style="font-size: 3em; margin-bottom: 0.5em;">{self.metadata.title}</h1>
            <h2 style="font-size: 1.5em; font-weight: normal; margin-bottom: 2em; color: #555;">
                {self.metadata.description or ''}
            </h2>
            <h3 style="font-size: 1.2em; margin-top: 4em;">{self.metadata.author}</h3>
            <p style="margin-top: 2em; font-size: 0.9em; color: #777;">
                Published by {self.metadata.publisher}<br/>
                {self.metadata.publication_date}
            </p>
        </div>
        """
        
        # Insert at the beginning of chapters
        original_chapters = self.chapters.copy()
        self.chapters.clear()
        
        self.add_chapter(
            title="Title Page",
            markdown_content=title_html, # Passing HTML directly works because markdown ignores valid block HTML
            is_frontmatter=True
        )
        
        # Restore other chapters
        for chap in original_chapters:
            self.chapters.append(chap)

    def _build_navigation_and_spine(self) -> None:
        """
        Constructs the Table of Contents (TOC), Navigation Control file for XML (NCX),
        and the reading order (Spine). Critical for Kindle compatibility.
        """
        logger.debug("Building TOC, NCX, and Spine reading order.")
        
        # Separate frontmatter and main content for TOC structuring
        toc_items = []
        spine_items = ['nav'] # 'nav' is the standard epub3 navigation page
        
        for chapter in self.chapters:
            if not chapter.epub_item:
                continue
                
            # Add to spine
            spine_items.append(chapter.epub_item)
            
            # Add to TOC (frontmatter can be excluded or included based on preference,
            # standard practice is to include them in the TOC).
            toc_items.append(epub.Link(chapter.file_name, chapter.title, chapter.id))

        self.book.toc = tuple(toc_items)

        # Add default NCX and Nav file
        # NCX is technically EPUB2, but highly recommended for KindleGen / Send-To-Kindle
        self.book.add_item(epub.EpubNcx())
        self.book.add_item(epub.EpubNav())

        # Define reading order
        self.book.spine = spine_items

    def build_epub(self, output_path: Union[str, Path]) -> str:
        """
        Compiles all added chapters, metadata, and styles into the final EPUB file.
        
        Args:
            output_path (Union[str, Path]): The destination file path (e.g., 'output/report.epub').
            
        Returns:
            str: The absolute path to the generated EPUB file.
        """
        path = Path(output_path)
        
        # Ensure output directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Building final EPUB at: {path}")
        
        try:
            self._build_navigation_and_spine()
            
            # Write the EPUB file using ebooklib
            epub.write_epub(str(path), self.book, {})
            
            logger.info(f"Successfully generated EPUB: {path.absolute()}")
            return str(path.absolute())
            
        except Exception as e:
            logger.error(f"Failed to build EPUB: {str(e)}")
            raise PipelineExportError(f"EPUB compilation failed: {e}")


# =============================================================================
# High-Level Pipeline Orchestrator Function
# =============================================================================

def export_research_to_epub(
    metadata_dict: Dict[str, Any],
    markdown_files: List[Union[str, Path]],
    output_filepath: Union[str, Path],
    include_auto_title_page: bool = True,
    cover_image_path: Optional[Union[str, Path]] = None
) -> str:
    """
    High-level pipeline function designed to be called by the Nex orchestration engine.
    Takes a list of generated markdown files and packages them into a production-ready EPUB.
    
    Args:
        metadata_dict (Dict[str, Any]): Dictionary containing title, author, description, etc.
        markdown_files (List[Union[str, Path]]): Ordered list of paths to markdown chapter files.
        output_filepath (Union[str, Path]): Desired output path for the .epub file.
        include_auto_title_page (bool): Whether to auto-generate a title page.
        cover_image_path (Optional[Union[str, Path]]): Path to cover image.
        
    Returns:
        str: The absolute path to the generated EPUB.
        
    Example:
        >>> metadata = {"title": "The Future of AGI", "author": "Nex Agent"}
        >>> files = ["chapter1.md", "chapter2.md"]
        >>> export_research_to_epub(metadata, files, "output.epub")
    """
    logger.info("Starting Nex EPUB pipeline export.")
    
    # Construct Metadata
    try:
        book_meta = BookMetadata(
            title=metadata_dict.get('title', 'Untitled Research Report'),
            author=metadata_dict.get('author', 'Nex Agent'),
            description=metadata_dict.get('description'),
            publisher=metadata_dict.get('publisher', 'Nex Autonomous Research'),
            subjects=metadata_dict.get('subjects', []),
            cover_image_path=cover_image_path
        )
    except Exception as e:
        raise MetadataError(f"Failed to parse metadata dictionary: {e}")

    # Initialize Adapter
    adapter = EpubPipelineAdapter(metadata=book_meta)
    
    # Process files
    for file_path in markdown_files:
        try:
            adapter.add_chapter_from_file(file_path=file_path)
        except FileNotFoundError as e:
            logger.warning(f"Skipping file due to error: {e}")
            continue
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            raise PipelineExportError(f"Pipeline failed at file {file_path}: {e}")

    # Add auto title page if requested
    if include_auto_title_page:
        adapter.generate_title_page()

    # Build and export
    final_path = adapter.build_epub(output_filepath)
    
    return final_path
"""