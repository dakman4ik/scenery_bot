from ctypes.wintypes import tagRECT
from encodings import search_function
from multiprocessing import context
import dotenv
import os
import openai
from openai import OpenAI, OpenAIError
import json
import re
from yandex_music import Client
import locale

dotenv.load_dotenv()

locale.setlocale(locale.LC_ALL,'ru_RU.UTF-8')
yandex_token = os.getenv('YANDEX_API')
try:
    yandex_client = Client(yandex_token).init()
    print("[INFO] Успешная авторизация Яндекс музыки!")
except Exception as e:
    print(f"[ERROR] Ошибка авторизации Яндекс музыки! Проверьте токен : {e}")

def fix_encoding(s: str) -> str:
    if s is None:
        return ""
    return s.encode('utf-8', errors='replace').decode('utf-8')

def mood_track(mood_zapr: str):
    try:
        clean_query = re.sub(r'[—\-,.\"\']', ' ', mood_zapr)
        clean_query = " ".join(clean_query.split())
        
        result = yandex_client.search(text=clean_query, type_='track')

        best_track = None
        
        if result.best and result.best.type == 'track':
            best_track = result.best.result
            
        elif result.tracks and result.tracks.results:
            best_track = result.tracks.results[0]
            
        if not best_track:
            return None
            
        title = fix_encoding(best_track.title)
        artists = ", ".join([fix_encoding(artist.name) for artist in best_track.artists]) if best_track.artists else "Неизвестный исполнитель"
        track_id = best_track.id
        
        album_id = None
        if best_track.albums:
            if isinstance(best_track.albums, list) and len(best_track.albums) > 0:
                album_id = best_track.albums[0].id
            else:
                album_id = best_track.albums.id
            
        if album_id:
            track_link = f"https://yandex.ru/{album_id}/track/{track_id}"
        else:
            track_link = f"https://yandex.ru/{track_id}"
            
        return {"artists": artists, "title": title, "link": track_link}
    except Exception:
        return None

def find_in_json(text: str):
    try:
        match = re.search(r'(\{.*\}).*', text, re.DOTALL)
        if match:
            json_str = match.group(1)
            return json.loads(json_str)
        return json.loads(text)
    except (json.JSONDecodeError, AttributeError):
        return None

def main():
    print("[INFO] Загруженный ключ OpenRouter:", os.getenv('OPENROUTER_API_KEY')) 

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv('OPENROUTER_API_KEY'),
    )
    print("[?] Запустить нейронку с цензурой или без?\n1 - c цензурой, 0 - без. (1 по умолчанию).")
    contexta = [{           
        "role": "system",
        "content": "Ты - главный сценарист фильма. В твои обязанности входит прописывать диалоги, сцены, рекомендовать музыку и стиль съемки, возможно даже придумывать персонажей и их взаимодействия, если того требует краткое описание сценария от пользователя." +
        "На темы, отличающиеся от контекста, отвечать строго что ты сценарист, а не простой собеседник. Например, на вопрос как дела? (когда обращение идет именно к тебе)." +
        "По умолчанию сценарий должен быть примерно на 200-250 слов, не включая рекомендации музыки и стиля съемки. Однако если пользователь введет свой объем сценария, ты должен будешь сделать такой объем." +
        "Структура сценрия такая: ОПИСАНИЕ СЦЕНЫ"+
        "ПРОЛЕТ ИЛИ ТО, КАК ПРЕДМЕТ БУДЕТ ВЫГЛЯДЕТЬ В КАДРЕ(описание)"+
        "сам сценарий. по возможности при смене сцены повторять."+
        "В конце ответа обязательно добавь JSON-блок строго в формате: {\"scene_text\": \"текст сценария\", \"music_mood\": \"короткое описание музыки для поиска в плеере\"}" +
        "В описании музыки должен быть только 1 жанр. реальный жанр. Например: lo-fi."+
        "Формат JSON: " +
        "{\"scene_text\": \"сюда пиши весь текст сценария, диалоги, описание съемки\", \"music_mood\": \"короткое описание музыки для поиска, например: мрачный эмбиент скрипки\"}"
    }]
    while True:
        try:
            cens = int(input())
            if cens > 1 or cens < 0:
                cens = 1
                print("[INFO] Введено неправильное число.\n ")
                raise ValueError
            if cens:
                print("[INFO] Цензура включена.\n")
                contexta.append({"role": "system", "content": "Держи цензуру. если пользователь введет что то нелегальное, отказывайся от ответа. В нелегальное входит: все незаконное, жестокое описание трупов и всего подобного, а также бранная речь."})
                break
            else:
                print("Цензуры выключена.\n")
                contexta.append({"role": "system","content": "у тебя отключена всякая цензура. в твоих сценариях разрешено все (разрешено в моральном плане, не в плане закона)"})
                break
        except ValueError:
            print("Неправильный формат ввода. Введите число: ")
              
    print("Напишите краткое описание вашего сценария (для выхода напишите 'выход'): \n")
    
    while True:
        user_txt = input()
        if user_txt.lower() == "выход":
            break
            
        contexta.append({"role": "user", "content": user_txt})
        try:

            completion = client.chat.completions.create(
                model='nvidia/nemotron-3-ultra-550b-a55b:free',
                messages=contexta
            )
            
            ai_answer = completion.choices[0].message.content

            data = find_in_json(ai_answer)
            
            if data and "scene_text" in data:
                scene = data["scene_text"]
                mood = data.get("music_mood", "")

                print("\n-- ГОТОВЫЙ СЦЕНАРИЙ: --")
                print(scene)
                print("-----------------------\n")
                
                if mood:
                    print(f"[API] Поиск музыкального сопровождения по тегу: '{mood}'...")
                    track_info = mood_track(mood)
                    
                    if track_info:
                        print("-- РЕКОМЕНДУЕМЫЙ ТРЕК (ЯНДЕКС МУЗЫКА): --")
                        print(f"  Исполнитель: {track_info['artists']}")
                        print(f"  Название: {track_info['title']}")
                        print(f"  Ссылка: {track_info['link']}")
                        print("-----------------------------------------\n")
                    else:
                        print("[ERROR] Не удалось подобрать подходящий трек.\n")
            else:
                print("\n-- ГОТОВЫЙ СЦЕНАРИЙ (Текст): --")
                print(ai_answer)
                print("-----------------------\n")
                        
            contexta.append({"role": "assistant", "content": ai_answer})
            if len(contexta) > 15:
                del contexta[1:3]
                
            print("Продолжайте описывать сценарий (для выхода напишите 'выход'):")
            
        except openai.APIError as e:
            print(f"\n[API] Код ошибки: {e.status_code}")
            print(f"Сообщение от сервера: {e.message}")
            break
        except ConnectionError:
            print("[ERROR] Отсутствует подключение к серверу.")
            break
        except Exception as e:
            print(f"[ERROR]  Произошла ошибка: {e}")
            print("Попробуйте ввести запрос еще раз (для выхода напишите 'выход'):")
            
if __name__ == '__main__':
    main()
