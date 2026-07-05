# Данные о картах Standoff 2

MAPS_DATA = {
    'rust': {
        'name': 'Rust',
        'wrong_answer': 'Arena',
        'description': '''Rust — это боевая арена в индустриальной тематике, предназначенная для режима «Обезвреживание бомбы». Она была впервые представлена в обновлении 0.10.0, заменив Zone 9, и с тех пор закрепилась в числе самых популярных карт среди игроков и команд, готовящихся к турнирам.'''
    },
    'sandstone': {
        'name': 'Sandstone',
        'wrong_answer': 'Dust',
        'description': '''Sandstone — карта с пустынной тематикой, вдохновленная классическими шутерами. Отличается открытыми пространствами и динамичным геймплеем.'''
    },
    'village': {
        'name': 'Village',
        'wrong_answer': 'Training Outside',
        'description': '''Village — карта для режимов со сценарием режима «Командный бой» в Standoff 2, добавленная в версии 0.7.0. Действия карты Village разворачиваются в Италии, неподалеку от карты Province.'''
    }
}

# Вопросы для теста (порядок важен!)
QUIZ_QUESTIONS = [
    {
        'map_key': 'rust',
        'correct_answer': 'Rust',
        'photo_path': 'data/photos/rust.jpg'  # Замените на свои пути к фото
    },
    {
        'map_key': 'sandstone',
        'correct_answer': 'Sandstone',
        'photo_path': 'data/photos/sandstone.jpg'
    },
    {
        'map_key': 'village',
        'correct_answer': 'Village',
        'photo_path': 'data/photos/village.jpg'
    }
]