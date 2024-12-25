import logging
import requests
import csv
import random
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes
from telegram.ext.filters import TEXT, COMMAND

# Logging setup
logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Google Sheets URLs
DECISION_POINTS_URL = "https://docs.google.com/spreadsheets/d/1sOqCrOl-kTKKQQ0ioYzYkqJwRM9qxsndxiLmo_RDZjI/export?format=csv&gid=0"
QUESTIONS_URL = "https://docs.google.com/spreadsheets/d/1sOqCrOl-kTKKQQ0ioYzYkqJwRM9qxsndxiLmo_RDZjI/export?format=csv&gid=1301413371"

# --- PHẦN 1: KHỞI TẠO ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Khởi tạo hệ thống và thông báo bắt đầu"""
    context.user_data.clear()
    context.user_data['current_game'] = "game_1"  # Trạng thái hiện tại
    context.user_data['used_scenarios'] = set()
    context.user_data['used_questions'] = set()
    context.user_data['scenario_count'] = 0
    context.user_data['question_count'] = 0
    context.user_data['total_stars'] = 0  # Điểm Game 1
    context.user_data['total_score'] = 0  # Điểm Game 2

    await update.message.reply_text(
        "🎮 **Chào mừng bạn đến với GameFi Nhập Vai!** 🎉\n\n"
        "⏩ Gõ /play để bắt đầu chơi Game 1: Kỹ năng xử lý tình huống.",
        parse_mode="Markdown"
    )

# --- PHẦN 2: GAME 1 - KỸ NĂNG XỬ LÝ TÌNH HUỐNG ---
async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bắt đầu Game 1"""
    if context.user_data['current_game'] != "game_1":
        await update.message.reply_text("❌ Game hiện tại không phải là Game 1. Gõ /start để bắt đầu lại.")
        return

    if context.user_data['scenario_count'] < 10:
        await play_scenario(update, context)
    else:
        # Hoàn thành Game 1, chuyển sang Game 2
        context.user_data['current_game'] = "game_2"
        await update.message.reply_text(
            "🎯 **Bạn đã hoàn thành Game 1: Kỹ năng xử lý tình huống!**\n\n"
            "✨ Chuyển sang Game 2: Khám phá sức mạnh trí tuệ của bạn!",
            parse_mode="Markdown"
        )
        await start_quiz(update, context)

async def play_scenario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý từng kịch bản trong Game 1"""
    scenarios = fetch_csv_data(DECISION_POINTS_URL)
    if not scenarios:
        await update.message.reply_text("❌ Không thể tải danh sách kịch bản. Vui lòng thử lại sau.")
        return

    unused_scenarios = [s for s in scenarios if s[0] not in context.user_data['used_scenarios']]
    if not unused_scenarios:
        await update.message.reply_text("⚠️ Không còn kịch bản nào mới để chơi.")
        return

    scenario = random.choice(unused_scenarios)
    context.user_data['used_scenarios'].add(scenario[0])
    context.user_data['current_scenario'] = scenario
    context.user_data['scenario_count'] += 1

    await update.message.reply_text(
        f"🗺️ *Kỹ năng xử lý tình huống {context.user_data['scenario_count']}*\n\n"
        f"{scenario[0]}\n\n"
        f"1️⃣ {scenario[1]}\n"
        f"2️⃣ {scenario[3]}\n\n"
        "⏩ Nhập 1 hoặc 2 để chọn.",
        parse_mode="Markdown"
    )

async def handle_choice_scenario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lựa chọn trong Game 1"""
    if context.user_data['current_game'] != "game_1":
        return

    user_choice = update.message.text.strip()
    current_scenario = context.user_data.get('current_scenario')

    if not current_scenario:
        await update.message.reply_text("❌ Không có kịch bản nào đang chạy. Gõ /play để bắt đầu.")
        return

    if user_choice not in ['1', '2']:
        await update.message.reply_text("❌ Vui lòng nhập 1 hoặc 2.")
        return

    if user_choice == '1':
        stars_earned = int(current_scenario[2])
        chosen_option = current_scenario[1]
    else:
        stars_earned = int(current_scenario[4])
        chosen_option = current_scenario[3]

    context.user_data['total_stars'] += stars_earned

    await update.message.reply_text(
        f"✅ Bạn đã chọn: {chosen_option}.\n"
        f"⭐ Bạn nhận được: {stars_earned} Game Star.\n"
        f"🌟 Tổng Game Star hiện tại: {context.user_data['total_stars']}.\n\n"
        "⏩ Chuyển sang tình huống tiếp theo...",
        parse_mode="Markdown"
    )

    await play(update, context)

# --- PHẦN 3: GAME 2 - KHÁM PHÁ SỨC MẠNH TRÍ TUỆ ---
async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bắt đầu Game 2"""
    if context.user_data['current_game'] != "game_2":
        return

    if context.user_data['question_count'] < 10:
        await play_question(update, context)
    else:
        await update.message.reply_text(
            f"🏁 **Bạn đã hoàn thành Game 2: Khám phá sức mạnh trí tuệ của bạn!**\n"
            f"⭐ Tổng Game Star: {context.user_data['total_stars']}\n"
            f"🧠 Tổng điểm: {context.user_data['total_score']} điểm.\n"
            "✨ Cảm ơn bạn đã tham gia!",
            parse_mode="Markdown"
        )

async def play_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị câu hỏi trong Game 2"""
    questions = fetch_csv_data(QUESTIONS_URL)
    if not questions:
        await update.message.reply_text("❌ Không thể tải danh sách câu hỏi. Vui lòng thử lại sau.")
        return

    unused_questions = [q for q in questions if q[0] not in context.user_data['used_questions']]
    if not unused_questions:
        await update.message.reply_text("⚠️ Không còn câu hỏi mới để chơi.")
        return

    question = random.choice(unused_questions)
    context.user_data['used_questions'].add(question[0])
    context.user_data['current_question'] = question
    context.user_data['question_count'] += 1

    await update.message.reply_text(
        f"🤔 *Khám phá sức mạnh trí tuệ của bạn - Câu {context.user_data['question_count']}*\n\n"
        f"{question[0]}\n\n"
        f"1️⃣ {question[1]}\n"
        f"2️⃣ {question[2]}\n"
        f"3️⃣ {question[3]}\n\n"
        "⏩ Nhập 1, 2 hoặc 3 để trả lời.",
        parse_mode="Markdown"
    )

async def handle_answer_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý câu trả lời trong Game 2"""
    if context.user_data.get('current_game') != "game_2":
        return

    user_choice = update.message.text.strip()
    current_question = context.user_data.get('current_question')

    if not current_question:
        await update.message.reply_text("❌ Không có câu hỏi nào đang chạy.")
        return

    if user_choice not in ['1', '2', '3']:
        await update.message.reply_text("❌ Vui lòng nhập 1, 2 hoặc 3.")
        return

    correct_answer = current_question[4].strip()
    if user_choice == correct_answer:
        context.user_data['total_score'] += 10  # Thêm điểm nếu đúng
        response = (
            f"✅ Đúng rồi! Bạn đã trả lời đúng.\n"
            f"🧠 Tổng điểm hiện tại: {context.user_data['total_score']} điểm."
        )
    else:
        response = (
            f"❌ Sai rồi! Đáp án đúng là: {correct_answer}.\n"
            f"🧠 Tổng điểm hiện tại: {context.user_data['total_score']} điểm."
        )

    await update.message.reply_text(response)

    # Chuyển sang câu hỏi tiếp theo
    await start_quiz(update, context)

# --- PHẦN 4: HÀM HỖ TRỢ ---
def fetch_csv_data(url):
    """Tải dữ liệu từ Google Sheets"""
    try:
        response = requests.get(url)
        response.raise_for_status()
        decoded_content = response.content.decode("utf-8")
        data = list(csv.reader(decoded_content.splitlines(), delimiter=","))
        return data[1:]  # Bỏ dòng tiêu đề
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        return []

# --- PHẦN 5: CHẠY BOT ---
def main():
    TOKEN = "7595985963:AAGoUSk8pIpAiSDaQwTufWqmYs3Kvn5mmt4"
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("play", play))
    application.add_handler(MessageHandler(TEXT & ~COMMAND, handle_choice_scenario))
    application.add_handler(MessageHandler(TEXT & ~COMMAND, handle_answer_question))

    application.run_polling()

if __name__ == "__main__":
    main()
