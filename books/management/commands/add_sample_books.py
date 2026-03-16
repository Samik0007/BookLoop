from django.core.management.base import BaseCommand
from books.models import Product

class Command(BaseCommand):
    help = 'Add sample books with various genres'

    def handle(self, *args, **kwargs):
        books_data = [
            # Self-Help / Personal Development
            {
                'Book_name': 'Think and Grow Rich',
                'Author': 'Napoleon Hill',
                'price': 450,
                'description': 'The legendary book that teaches the secrets of success and wealth building through the power of thought.',
                'genre': 'Self-Help',
                'quantity': 15
            },
            {
                'Book_name': 'The 7 Habits of Highly Effective People',
                'Author': 'Stephen Covey',
                'price': 550,
                'description': 'Timeless wisdom on personal effectiveness and leadership that has transformed millions of lives.',
                'genre': 'Self-Help',
                'quantity': 20
            },
            {
                'Book_name': 'How to Win Friends and Influence People',
                'Author': 'Dale Carnegie',
                'price': 400,
                'description': 'The classic guide to building better relationships and effective communication skills.',
                'genre': 'Self-Help',
                'quantity': 18
            },
            {
                'Book_name': 'You Can Win',
                'Author': 'Shiv Khera',
                'price': 350,
                'description': 'Inspirational book about achieving success through positive attitude and determination.',
                'genre': 'Self-Help',
                'quantity': 25
            },
            {
                'Book_name': 'The Power of Now',
                'Author': 'Eckhart Tolle',
                'price': 480,
                'description': 'A spiritual guide to enlightenment and living in the present moment.',
                'genre': 'Self-Help',
                'quantity': 12
            },
            
            # Fiction
            {
                'Book_name': '1984',
                'Author': 'George Orwell',
                'price': 420,
                'description': 'Dystopian novel about totalitarianism and surveillance in a futuristic society.',
                'genre': 'Fiction',
                
                'quantity': 20
            },
            {
                'Book_name': 'To Kill a Mockingbird',
                'Author': 'Harper Lee',
                'price': 450,
                'description': 'Classic novel about racial injustice and childhood innocence in the American South.',
                'genre': 'Fiction',
                
                'quantity': 15
            },
            {
                'Book_name': 'The Great Gatsby',
                'Author': 'F. Scott Fitzgerald',
                'price': 380,
                'description': 'A tale of wealth, love, and the American Dream in the Jazz Age.',
                'genre': 'Fiction',
                
                'quantity': 18
            },
            {
                'Book_name': 'Pride and Prejudice',
                'Author': 'Jane Austen',
                'price': 420,
                'description': 'Romantic novel about manners, upbringing, and marriage in Georgian England.',
                'genre': 'Fiction',
                
                'quantity': 16
            },
            {
                'Book_name': 'The Catcher in the Rye',
                'Author': 'J.D. Salinger',
                'price': 400,
                'description': 'Coming-of-age story about teenage rebellion and alienation.',
                'genre': 'Fiction',
                
                'quantity': 14
            },
            
            # Science Fiction / Fantasy
            {
                'Book_name': 'The Hobbit',
                'Author': 'J.R.R. Tolkien',
                'price': 550,
                'description': 'Epic fantasy adventure following Bilbo Baggins on his unexpected journey.',
                'genre': 'Fantasy',
                
                'quantity': 22
            },
            {
                'Book_name': 'Harry Potter and the Sorcerer\'s Stone',
                'Author': 'J.K. Rowling',
                'price': 600,
                'description': 'The magical beginning of Harry Potter\'s adventures at Hogwarts School.',
                'genre': 'Fantasy',
                
                'quantity': 30
            },
            {
                'Book_name': 'Dune',
                'Author': 'Frank Herbert',
                'price': 650,
                'description': 'Science fiction masterpiece about politics, religion, and ecology on the desert planet Arrakis.',
                'genre': 'Science Fiction',
                
                'quantity': 15
            },
            {
                'Book_name': 'The Chronicles of Narnia',
                'Author': 'C.S. Lewis',
                'price': 700,
                'description': 'Beloved fantasy series about children discovering a magical world.',
                'genre': 'Fantasy',
                
                'quantity': 18
            },
            {
                'Book_name': 'Ender\'s Game',
                'Author': 'Orson Scott Card',
                'price': 480,
                'description': 'Military science fiction about a young genius trained to save humanity.',
                'genre': 'Science Fiction',
                
                'quantity': 16
            },
            
            # Mystery / Thriller
            {
                'Book_name': 'The Da Vinci Code',
                'Author': 'Dan Brown',
                'price': 520,
                'description': 'Mystery thriller involving art, symbols, and ancient secrets.',
                'genre': 'Thriller',
                
                'quantity': 20
            },
            {
                'Book_name': 'Gone Girl',
                'Author': 'Gillian Flynn',
                'price': 480,
                'description': 'Psychological thriller about a marriage gone terrifyingly wrong.',
                'genre': 'Thriller',
                
                'quantity': 18
            },
            {
                'Book_name': 'The Girl with the Dragon Tattoo',
                'Author': 'Stieg Larsson',
                'price': 550,
                'description': 'Gripping mystery about a journalist and a hacker solving a cold case.',
                'genre': 'Mystery',
                
                'quantity': 17
            },
            {
                'Book_name': 'And Then There Were None',
                'Author': 'Agatha Christie',
                'price': 400,
                'description': 'Classic mystery where ten strangers are invited to an island and murdered one by one.',
                'genre': 'Mystery',
                
                'quantity': 15
            },
            {
                'Book_name': 'The Silence of the Lambs',
                'Author': 'Thomas Harris',
                'price': 460,
                'description': 'Psychological horror thriller featuring the infamous Hannibal Lecter.',
                'genre': 'Thriller',
                
                'quantity': 14
            },
            
            # Non-Fiction / Biography
            {
                'Book_name': 'Steve Jobs',
                'Author': 'Walter Isaacson',
                'price': 650,
                'description': 'Authorized biography of Apple co-founder Steve Jobs.',
                'genre': 'Biography',
                
                'quantity': 20
            },
            {
                'Book_name': 'Sapiens: A Brief History of Humankind',
                'Author': 'Yuval Noah Harari',
                'price': 600,
                'description': 'Explores the history of humanity from the Stone Age to the modern age.',
                'genre': 'Non-Fiction',
                
                'quantity': 25
            },
            {
                'Book_name': 'Educated',
                'Author': 'Tara Westover',
                'price': 520,
                'description': 'Memoir about a woman who grows up in a survivalist family and eventually earns a PhD.',
                'genre': 'Biography',
                
                'quantity': 18
            },
            {
                'Book_name': 'Becoming',
                'Author': 'Michelle Obama',
                'price': 680,
                'description': 'Memoir by the former First Lady of the United States.',
                'genre': 'Biography',
                
                'quantity': 22
            },
            {
                'Book_name': 'The Immortal Life of Henrietta Lacks',
                'Author': 'Rebecca Skloot',
                'price': 550,
                'description': 'True story of Henrietta Lacks and her immortal cell line that revolutionized medicine.',
                'genre': 'Non-Fiction',
                
                'quantity': 15
            },
            
            # Business / Economics
            {
                'Book_name': 'Rich Dad Poor Dad',
                'Author': 'Robert Kiyosaki',
                'price': 450,
                'description': 'Personal finance book about financial literacy and building wealth.',
                'genre': 'Business',
                
                'quantity': 28
            },
            {
                'Book_name': 'The Lean Startup',
                'Author': 'Eric Ries',
                'price': 520,
                'description': 'Revolutionary approach to building and managing startups.',
                'genre': 'Business',
                
                'quantity': 20
            },
            {
                'Book_name': 'Zero to One',
                'Author': 'Peter Thiel',
                'price': 480,
                'description': 'Notes on startups and how to build the future.',
                'genre': 'Business',
                
                'quantity': 18
            },
            {
                'Book_name': 'Thinking, Fast and Slow',
                'Author': 'Daniel Kahneman',
                'price': 600,
                'description': 'Explores the two systems that drive the way we think and make decisions.',
                'genre': 'Psychology',
                
                'quantity': 16
            },
            {
                'Book_name': 'Good to Great',
                'Author': 'Jim Collins',
                'price': 550,
                'description': 'Why some companies make the leap to greatness and others don\'t.',
                'genre': 'Business',
                
                'quantity': 17
            },
            
            # Romance
            {
                'Book_name': 'The Notebook',
                'Author': 'Nicholas Sparks',
                'price': 380,
                'description': 'Heartwarming love story about enduring romance.',
                'genre': 'Romance',
                
                'quantity': 20
            },
            {
                'Book_name': 'Me Before You',
                'Author': 'Jojo Moyes',
                'price': 420,
                'description': 'Moving love story about a caregiver and her patient.',
                'genre': 'Romance',
                
                'quantity': 18
            },
            {
                'Book_name': 'The Fault in Our Stars',
                'Author': 'John Green',
                'price': 400,
                'description': 'Young adult romance about two teens with cancer who fall in love.',
                'genre': 'Romance',
                
                'quantity': 22
            },
            {
                'Book_name': 'Outlander',
                'Author': 'Diana Gabaldon',
                'price': 550,
                'description': 'Time-traveling historical romance adventure.',
                'genre': 'Romance',
                
                'quantity': 15
            },
            {
                'Book_name': 'P.S. I Love You',
                'Author': 'Cecelia Ahern',
                'price': 390,
                'description': 'Emotional story about love, loss, and moving forward.',
                'genre': 'Romance',
                
                'quantity': 16
            },
        ]

        created_count = 0
        skipped_count = 0

        for book_data in books_data:
            book, created = Product.objects.get_or_create(
                Book_name=book_data['Book_name'],
                defaults=book_data
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created: {book_data["Book_name"]}'))
            else:
                skipped_count += 1
                self.stdout.write(self.style.WARNING(f'- Skipped (already exists): {book_data["Book_name"]}'))

        self.stdout.write(self.style.SUCCESS(f'\n📚 Summary:'))
        self.stdout.write(self.style.SUCCESS(f'   Created: {created_count} books'))
        self.stdout.write(self.style.WARNING(f'   Skipped: {skipped_count} books'))
        self.stdout.write(self.style.SUCCESS(f'   Total in database: {Product.objects.count()} books'))
