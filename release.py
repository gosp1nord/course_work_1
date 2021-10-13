import json
import os
import requests
import time


def get_id_vk(user, token_vk):
    url = f"https://api.vk.com/method/users.get"
    params = {
        'user_ids': user,
        'fields': 'id',
        'access_token': token_vk,
        'v': '5.89'
    }
    response = requests.get(url, params=params)
    id = 0
    if response.status_code == 200:
        data = response.json()
        if 'error' in data:
            print("Ошибка поиска пользователя VK:")
            print(data["error"]["error_msg"])
        elif 'deactivated' in data['response'][0]:
            print(f"Страница пользователя {user} удалена или заблокирована")
        elif data['response'][0]['is_closed']:
            name = f"{data['response'][0]['first_name']} {data['response'][0]['last_name']}"
            print(f'Страница пользователя "{name}" скрыта настройками приватности')
        else:
            id = data['response'][0]['id']
    else:
        print("Ошибка при обращении к серверу VK при проверке пользователя")
    return id


def get_all_photos_vk(user_id, token_vk, count_photos):
    params = {
        'owner_id': user_id,
        'extended': '1',
        'photo_sizes': '1',
        'album_id': 'profile',
        'count': count_photos,
        'access_token': token_vk,
        'v': '5.131'
    }
    url = f"https://api.vk.com/method/photos.get"
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print("Ошибка при выполнении запроса к серверу ВКонтакте на получение списка id фото. Код ошибки: ", response.status_code)
        return False
    data = response.json()
    if 'error' in data:
        print("Ошибка в ответе от сервера ВКонтакте при запросе на получение списка id фото:")
        print(data["error"]["error_msg"])
        return False
    list_photos = []
    for i in range(len(data['response']['items'])):
        photo_count_sizes = len(data['response']['items'][i]['sizes'])
        photo_last_size = data['response']['items'][i]['sizes'][photo_count_sizes - 1]['type']
        photo_url_last_size = data['response']['items'][i]['sizes'][photo_count_sizes - 1]['url']
        photo_likes = data['response']['items'][i]['likes']['count']
        photo_date = data['response']['items'][i]['date']
        list_photos.append({
            'photo_date': photo_date,
            'photo_last_size': photo_last_size,
            'photo_url_last_size': photo_url_last_size,
            'photo_likes': photo_likes
        })
    return list_photos


def create_folder(token, name):
    url = 'https://cloud-api.yandex.net/v1/disk/resources'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'OAuth {token}'
    }
    params = {
        'path': name
    }
    response = requests.put(url=url, headers=headers, params=params)
    if response.status_code == 201:
        print(f'На Яндекс-диске создана папка с именем "{name}" для хранения фотографий')
    elif response.status_code == 409:
        print(f'Папка с именем "{name}" уже существует, будем записывать в нее')
    else:
        print('Ошибка при создании папки: ', response.json()['message'])
        exit()


def get_load_link_from_yadisk(token, path_to_file):
    url = 'https://cloud-api.yandex.net/v1/disk/resources/upload'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'OAuth {token}'
    }
    params = {
        'path': path_to_file,
        'overwrite': 'true'
    }
    load_link = requests.get(url=url, headers=headers, params=params)
    return load_link.json()


def load_to_yadisk(token, path_to_file, file_name):
    path = f'{path_to_file}/{file_name}'
    url = get_load_link_from_yadisk(token, path).get('href')
    if url:
        response = requests.put(url, data=open(file_name, "rb"))
        return response.status_code
    else:
        print("Не удалось получить ссылку на загрузку файла от Я-диска")
        return 404


def photos_from_vk_to_yadisk(user_id, folder, token_vk, token_yadisk, count_photos=5):
    create_folder(token_yadisk, folder)

    list_photos = get_all_photos_vk(user_id, token_vk, count_photos)
    if list_photos is False:
        return "Ни одного фото получить не удалось"
    list_info = []
    for item in list_photos:
        url = item['photo_url_last_size']
        photo_size = item['photo_last_size']
        file_name = f"{item['photo_likes']}_{item['photo_date']}.jpg"
        try:
            response = requests.get(url)
        except Exception as e:
            print(e)
            return "Что-то пошло не так при скачивании фотографии из VK"
        time.sleep(0.5)
        with open(file_name, 'wb') as file:
            file.write(response.content)

        res_code = load_to_yadisk(token_yadisk, folder, file_name)
        if res_code == 201:
            print(f"Фото {file_name} сохранено")
        else:
            return "Ошибка загрузки фото на Я-диск"

        try:
            os.remove(file_name)
        except Exception as ex:
            print("Ошибка при удалении временного файла фото на локальном диске")
            print(ex)

        list_info.append({'file_name': file_name, 'size': photo_size})

    if list_info:
        with open('info.json', 'w') as file:
            json.dump(list_info, file, indent=2, ensure_ascii=False)
        return "Все фото загружены на Яндекс-диск"
    else:
        return "Ни одной фотографии скачать не удалось"


if __name__ == '__main__':
    token_vk = "958eb5d439726565e9333aa30e50e0f937ee432e927f0dbd541c541887d919a7c56f95c04217915c32008"
    token_yadisk = '0'
    if token_yadisk == '0':
        print("В программе нет токена для Я-диска")
        exit()

    while True:
        user = input("Ввести логин или id пользователя VK: ")
        user_id = get_id_vk(user, token_vk)
        if user_id != 0:
            break

    while True:
        folder = input("Ввести название папки, в которой будут храниться фотографии на Я-диске: ")
        if '/' in folder:
            print("Имя папки не может содержать символ '/'")
        else:
            break

    while True:
        count_photos = input("По-умолчанию будет скачано 5 фотографий. Введите нужное количество фото (но не более 1000) или просто нажмите Enter: ")
        if count_photos:
            if count_photos.isdigit():
                count_photos = int(count_photos)
                if 0 < count_photos < 1001:
                    print(f"Скачаем {count_photos} фото")
                    break
                else:
                    print("Недопустимая цифра, можно найти не меньше 1 и не больше 1000")
            else:
                print("Вводить только цифры!")
        else:
            count_photos = 5
            print("ОК, ищем 5 фоток")
            break

    result = photos_from_vk_to_yadisk(user_id, folder, token_vk, token_yadisk, count_photos=count_photos)
    print(result)




