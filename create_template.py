import pandas as pd

# Tạo dataframe mẫu
data = {
    "content": ["Câu hỏi ví dụ 1", "Câu hỏi ví dụ 2"],
    "option_a": ["Đáp án A1", "Đáp án A2"],
    "option_b": ["Đáp án B1", "Đáp án B2"],
    "option_c": ["Đáp án C1", "Đáp án C2"],
    "option_d": ["Đáp án D1", "Đáp án D2"],
    "correct_option": ["A", "C"]
}

df = pd.DataFrame(data)

# Lưu file vào thư mục static
df.to_excel("static/sample_questions.xlsx", index=False)
print("✅ Đã tạo file mẫu: static/sample_questions.xlsx")
