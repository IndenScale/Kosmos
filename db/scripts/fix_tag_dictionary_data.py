import sqlite3
import json

def fix_tag_dictionary_data():
    """修复tag_dictionary字段的数据格式"""
    conn = sqlite3.connect('c:\\Users\\mi\\Documents\\Kosmos\\data\\db\\kosmos.db')
    cursor = conn.cursor()

    # 查询所有知识库
    cursor.execute("SELECT id, tag_dictionary FROM knowledge_bases")
    rows = cursor.fetchall()

    for kb_id, tag_dict in rows:
        if tag_dict:
            try:
                # 尝试解析JSON，如果成功说明格式正确
                parsed = json.loads(tag_dict)
                print(f"KB {kb_id}: tag_dictionary format is correct")
            except (json.JSONDecodeError, TypeError):
                # 如果解析失败，重置为空字典
                print(f"KB {kb_id}: fixing invalid tag_dictionary")
                cursor.execute(
                    "UPDATE knowledge_bases SET tag_dictionary = ? WHERE id = ?",
                    ("{}", kb_id)
                )

    conn.commit()
    conn.close()
    print("Data fix completed")

if __name__ == "__main__":
    fix_tag_dictionary_data()