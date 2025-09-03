import pandas as pd
import os
import time
from llm import query_llm  # 假设你实现了 query_llm(prompt: str) -> str

def process_excel_data(excel_file, start_row=1):
    """
    读取 Excel 中的数据，从指定行开始处理，用 LLM 返回结果，
    并将结果（仅 response）追加保存到 llm_results.txt 中。
    """
    try:
        df = pd.read_excel(excel_file)

        if df.empty:
            print(f"Excel文件 {excel_file} 中没有数据")
            return []

        print(f"读取 {len(df)} 行数据，从第 {start_row+1} 行开始处理")

        results = []
        output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "llm_results.txt")

        for i in range(start_row, len(df)):
            row = df.iloc[i]
            prompt = " ".join([str(val) for val in row.values if pd.notna(val)])

            print(f"\n处理第 {i+1}/{len(df)} 行")
            print(f"Prompt: {prompt}")

            response = query_llm(prompt)

            if response:
                print("回答：", response)
                results.append(response)

                # 仅保存 response 到文件
                with open(output_file, "a", encoding="utf-8") as f:
                    f.write(response + "\n")  # 每条 response 占一行
            else:
                print("获取响应失败")

            if i < len(df) - 1:
                time.sleep(1)

        print(f"\n处理完成，共保存 {len(results)} 条回答")
        return results

    except Exception as e:
        print(f"处理出错: {e}")
        return []

def main():
    excel_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "overwork02llm.xlsx")
    start_row = 0
    process_excel_data(excel_file, start_row)

if __name__ == "__main__":
    main()
