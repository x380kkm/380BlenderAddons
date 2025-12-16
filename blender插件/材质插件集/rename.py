import os
import shutil
import datetime

def main():
    # 获取脚本所在的当前路径
    current_dir = os.getcwd()
    script_name = os.path.basename(__file__) # 获取脚本自己的名字，防止备份时把自己也拷进去

    # 1. 扫描 OBJ 文件
    obj_files = [f for f in os.listdir(current_dir) if f.lower().endswith('.obj')]

    if not obj_files:
        print("❌ 未找到 .obj 文件。")
        input("按回车键退出...")
        return

    print(f"📂 扫描到 {len(obj_files)} 个 OBJ 文件。")
    print("-" * 40)
    print("⚠️  本脚本将执行以下操作：")
    print("   1. 【全量备份】将当前文件夹所有内容复制到一个新的备份文件夹。")
    print("   2. 【修改文件】将原 OBJ 文件内部的物体名修改为文件名。")
    print("-" * 40)

    # 2. 确认环节
    confirm = input(">>> 确认执行? (输入 y 并回车): ").strip().lower()
    if confirm != 'y':
        print("操作已取消。")
        input("按回车键退出...")
        return

    # ================= 阶段一：自动备份 =================
    print("\n📦 [1/2] 正在创建备份...")
    
    # 生成备份文件夹名称 (Backup_年月日_时分秒)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_folder_name = f"Backup_{timestamp}"
    backup_path = os.path.join(current_dir, backup_folder_name)

    try:
        os.makedirs(backup_path) # 创建备份目录
        
        # 遍历当前目录所有文件和文件夹
        for item in os.listdir(current_dir):
            # 跳过 备份文件夹自身 和 脚本自身
            if item == backup_folder_name or item == script_name:
                continue

            src = os.path.join(current_dir, item)
            dst = os.path.join(backup_path, item)

            if os.path.isdir(src):
                shutil.copytree(src, dst) # 复制文件夹
            else:
                shutil.copy2(src, dst)    # 复制文件
        
        print(f"✅ 备份完成！所有原始文件已保存至: ./{backup_folder_name}/")

    except Exception as e:
        print(f"❌ 备份失败: {e}")
        print("为了安全，脚本停止执行。")
        input("按回车键退出...")
        return

    # ================= 阶段二：修改 OBJ =================
    print("\n🛠️  [2/2] 开始修改 OBJ 文件名称...")
    
    count_success = 0
    count_skipped = 0

    for filename in obj_files:
        file_path = os.path.join(current_dir, filename)
        name_pure = os.path.splitext(filename)[0]

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            # 检查内部物体数量
            target_indices = [i for i, line in enumerate(lines) if line.startswith(('o ', 'g '))]

            if len(target_indices) > 1:
                print(f"   ⏭️  [跳过] {filename} (含多个物体)")
                count_skipped += 1
                continue
            
            # 修改逻辑
            if len(target_indices) == 1:
                # 替换已有的一行
                lines[target_indices[0]] = f"o {name_pure}\n"
            else:
                # 没有任何命名，插入到第一行
                lines.insert(0, f"o {name_pure}\n")

            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
            print(f"   ✅ [成功] {filename}")
            count_success += 1

        except Exception as e:
            print(f"   ❌ [错误] {filename}: {e}")

    # ================= 结束 =================
    print("\n" + "="*40)
    print(f"🎉 全部完成。")
    print(f"   备份位置: {backup_folder_name}")
    print(f"   修改数量: {count_success}")
    print(f"   跳过数量: {count_skipped}")
    
    # 这一行确保双击运行时窗口不会立刻消失
    input("\n按回车键退出...")

if __name__ == "__main__":
    main()