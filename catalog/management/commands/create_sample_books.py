from django.core.management.base import BaseCommand
from django.utils import timezone
from catalog.models import (
    Author,
    Publisher,
    Category,
    Book,
    BookAuthor,
    BookCategory,
    BookItem,
)
from datetime import date


class Command(BaseCommand):
    help = "Create sample books with authors for testing CRUD functionality"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Creating sample books..."))

        # Create sample publishers
        publisher1, _ = Publisher.objects.get_or_create(
            name="Penguin Random House",
            defaults={
                "description": "Major publishing company",
                "founded_year": 1927,
                "website": "https://penguinrandomhouse.com",
            },
        )

        publisher2, _ = Publisher.objects.get_or_create(
            name="HarperCollins",
            defaults={
                "description": "Global publishing company",
                "founded_year": 1989,
                "website": "https://harpercollins.com",
            },
        )

        # Create sample categories
        fiction_cat, _ = Category.objects.get_or_create(
            name="Fiction",
            defaults={"slug": "fiction", "description": "Fictional literature"},
        )

        scifi_cat, _ = Category.objects.get_or_create(
            name="Science Fiction",
            defaults={
                "slug": "science-fiction",
                "description": "Science fiction literature",
                "parent": fiction_cat,
            },
        )

        nonfiction_cat, _ = Category.objects.get_or_create(
            name="Non-Fiction",
            defaults={"slug": "non-fiction", "description": "Non-fictional books"},
        )

        # Create sample authors
        author1, _ = Author.objects.get_or_create(
            name="Isaac Asimov",
            defaults={
                "biography": (
                    "American writer and professor of biochemistry "
                    "at Boston University"
                ),
                "birth_date": date(1920, 1, 2),
                "death_date": date(1992, 4, 6),
            },
        )

        author2, _ = Author.objects.get_or_create(
            name="Arthur C. Clarke",
            defaults={
                "biography": (
                    "British science fiction writer, science writer, "
                    "futurist, inventor, undersea explorer, "
                    "and television series host"
                ),
                "birth_date": date(1917, 12, 16),
                "death_date": date(2008, 3, 19),
            },
        )

        author3, _ = Author.objects.get_or_create(
            name="Frank Herbert",
            defaults={
                "biography": (
                    "American science fiction author best known "
                    "for the 1965 novel Dune"
                ),
                "birth_date": date(1920, 10, 8),
                "death_date": date(1986, 2, 11),
            },
        )

        author4, _ = Author.objects.get_or_create(
            name="Ray Bradbury",
            defaults={
                "biography": (
                    "American author and screenwriter known for "
                    "his fantasy, science fiction, horror, "
                    "and mystery fiction"
                ),
                "birth_date": date(1920, 8, 22),
                "death_date": date(2012, 6, 5),
            },
        )

        # Create sample books
        books_data = [
            {
                "title": "Foundation",
                "description": (
                    "The first novel in the Foundation series, "
                    "about a galactic empire in decline"
                ),
                "isbn13": "9780553293357",
                "publish_year": 1951,
                "pages": 244,
                "language_code": "en",
                "publisher": publisher1,
                "authors": [author1],
                "categories": [scifi_cat],
            },
            {
                "title": "2001: A Space Odyssey",
                "description": (
                    "A science fiction novel about human evolution, "
                    "artificial intelligence, and extraterrestrial life"
                ),
                "isbn13": "9780451457998",
                "publish_year": 1968,
                "pages": 297,
                "language_code": "en",
                "publisher": publisher2,
                "authors": [author2],
                "categories": [scifi_cat],
            },
            {
                "title": "Dune",
                "description": (
                    "A science fiction epic set in the distant "
                    "future amidst a feudal interstellar society"
                ),
                "isbn13": "9780441172719",
                "publish_year": 1965,
                "pages": 688,
                "language_code": "en",
                "publisher": publisher1,
                "authors": [author3],
                "categories": [scifi_cat],
            },
            {
                "title": "Fahrenheit 451",
                "description": (
                    "A dystopian novel about a future society " "where books are burned"
                ),
                "isbn13": "9781451673319",
                "publish_year": 1953,
                "pages": 249,
                "language_code": "en",
                "publisher": publisher2,
                "authors": [author4],
                "categories": [scifi_cat, fiction_cat],
            },
            {
                "title": "The Caves of Steel",
                "description": (
                    "A science fiction detective novel combining "
                    "the mystery and robot stories"
                ),
                "isbn13": "9780553293395",
                "publish_year": 1954,
                "pages": 206,
                "language_code": "en",
                "publisher": publisher1,
                "authors": [author1],
                "categories": [scifi_cat],
            },
        ]

        created_books = []
        for book_data in books_data:
            # Extract authors and categories
            authors = book_data.pop("authors")
            categories = book_data.pop("categories")

            # Create or get the book
            book, created = Book.objects.get_or_create(
                title=book_data["title"], defaults=book_data
            )

            if created:
                created_books.append(book)

                # Add authors
                for idx, author in enumerate(authors, 1):
                    BookAuthor.objects.get_or_create(
                        book=book, author=author, defaults={"author_order": idx}
                    )

                # Add categories
                for category in categories:
                    BookCategory.objects.get_or_create(book=book, category=category)

                # Create sample book items
                for i in range(2):  # Create 2 items per book
                    BookItem.objects.get_or_create(
                        book=book,
                        barcode=f"{book.isbn13}-{i+1:02d}",
                        defaults={
                            "status": BookItem.Status.AVAILABLE,
                            "location_code": (f"A{(book.id % 10) + 1:02d}-{i+1:02d}"),
                        },
                    )

                self.stdout.write(self.style.SUCCESS(f"Created book: {book.title}"))
            else:
                self.stdout.write(
                    self.style.WARNING(f"Book already exists: {book.title}")
                )

        if created_books:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nSuccessfully created {len(created_books)} books "
                    f"with authors, categories, and items!"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING("All books already exist in the database.")
            )

        # Show summary
        self.stdout.write(self.style.SUCCESS(f"\nDatabase Summary:"))
        self.stdout.write(f"- Authors: {Author.objects.count()}")
        self.stdout.write(f"- Publishers: {Publisher.objects.count()}")
        self.stdout.write(f"- Categories: {Category.objects.count()}")
        self.stdout.write(f"- Books: {Book.objects.count()}")
        self.stdout.write(f"- Book Items: {BookItem.objects.count()}")
