bl_info = {
    "name": "SBSAR工具箱",
    "author": "380kkm (Modified by Gemini)",
    "version": (2, 2),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > SBSAR工具",
    "description": "类似我了,不过至少比unity插件强",
    "category": "3D View"
}

import bpy
import os
import math
from mathutils import Vector

# =============================================================================
# 全局工具函数：带深度的文件扫描
# =============================================================================

def scan_files_with_depth(root_path, depth, extensions):
    """
    遍历文件夹，受限于最大深度。
    返回: [(folder_name, [file_paths...]), ...]
    """
    root_path = os.path.abspath(root_path)
    root_depth = root_path.rstrip(os.path.sep).count(os.path.sep)
    
    found_groups = []
    
    for root, dirs, files in os.walk(root_path):
        # 计算当前深度
        current_depth = root.rstrip(os.path.sep).count(os.path.sep) - root_depth
        
        # 如果超出深度，修改 dirs 列表以停止 os.walk 继续向下
        if current_depth >= depth:
            del dirs[:]
            
        # 筛选文件
        valid_files = [
            os.path.join(root, f) for f in files 
            if f.lower().endswith(extensions)
        ]
        
        if valid_files:
            folder_name = os.path.basename(root)
            # 如果是根目录，名字可能为空或路径名，做个处理
            if not folder_name: 
                folder_name = os.path.basename(root_path)
            found_groups.append((folder_name, valid_files))
            
    return found_groups

def create_preview_geometry(name, location, material):
    """创建统一的预览几何体 (球 + 板)"""
    # 1. 创建板
    bpy.ops.mesh.primitive_plane_add(size=2.0, location=(location[0], location[1], 0))
    plane = bpy.context.active_object
    plane.name = f"{name}_Plane"
    if material:
        if not plane.data.materials:
            plane.data.materials.append(material)
        else:
            plane.data.materials[0] = material

    # 2. 创建球
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.6, location=(location[0], location[1], 0.6))
    sphere = bpy.context.active_object
    sphere.name = f"{name}_Sphere"
    bpy.ops.object.shade_smooth()
    if material:
        if not sphere.data.materials:
            sphere.data.materials.append(material)
        else:
            sphere.data.materials[0] = material
            
    # 将两个物体放入一个新的集合（可选，为了整洁，这里暂时不放，保持选中状态）
    return plane, sphere

# =============================================================================
# 功能 1：PBR 导入 (仅导入，不生成物体)
# =============================================================================

texture_type_mapping = {
    "_c": "BaseColor", "_n": "Normal", "_e": "Emission", "_ao": "AmbientOcclusion",
    "_r": "Roughness", "_m": "Metallic", "_arm": "ARM", "_d": "Displacement",
    "_h": "Displacement", "_o": "Alpha", "base": "BaseColor", "color": "BaseColor",
    "diffuse": "BaseColor", "albedo": "BaseColor", "col": "BaseColor",
    "emissive": "Emission", "emission": "Emission", "metallic": "Metallic",
    "metalness": "Metallic", "roughness": "Roughness", "normal": "Normal",
    "nrm": "Normal", "bump": "Bump", "height": "Displacement",
    "displacement": "Displacement", "disp": "Displacement", "opacity": "Alpha",
    "alpha": "Alpha", "ao": "AmbientOcclusion",
}

def load_texture_node(material, texture_path, label, location, is_color=True):
    nodes = material.node_tree.nodes
    node = nodes.new(type='ShaderNodeTexImage')
    try:
        node.image = bpy.data.images.load(texture_path)
    except:
        return node
    node.label = label
    node.location = location
    if not is_color:
        if hasattr(node.image, 'colorspace_settings'):
            node.image.colorspace_settings.is_data = True
            try:
                node.image.colorspace_settings.name = 'Non-Color'
            except:
                pass 
    return node

def create_pbr_material(material, texture_files):
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    for node in nodes: nodes.remove(node)

    principled_node = nodes.new(type='ShaderNodeBsdfPrincipled')
    principled_node.location = Vector((200, -200))
    output_node = nodes.new(type='ShaderNodeOutputMaterial')
    output_node.location = Vector((600, -200))
    links.new(principled_node.outputs['BSDF'], output_node.inputs['Surface'])

    ordered_texture_files = {key: None for key in set(texture_type_mapping.values())}
    for file_path in texture_files:
        base_name = os.path.splitext(os.path.basename(file_path))[0].lower()
        if "sheenopacity" in base_name: continue
        texture_type = None
        for key, type_name in texture_type_mapping.items():
            if base_name.endswith(key):
                texture_type = type_name
                break
        if not texture_type:
             texture_type = next((v for k, v in texture_type_mapping.items() if k in base_name), None)
        if texture_type and ordered_texture_files[texture_type] is None:
            ordered_texture_files[texture_type] = file_path

    offset_y = 0
    texture_nodes = {}
    normal_map_node = None 
    process_order = ["BaseColor", "ARM", "Metallic", "Roughness", "Emission", "Normal", "Bump", "Alpha", "Displacement", "AmbientOcclusion"]

    for texture_type in process_order:
        file_path = ordered_texture_files.get(texture_type)
        if file_path:
            is_color_data = texture_type in ["BaseColor", "Emission"]
            texture_node = load_texture_node(material, file_path, texture_type, Vector((-400, offset_y)), is_color_data)
            texture_nodes[texture_type] = texture_node

            if texture_type == "BaseColor":
                links.new(texture_node.outputs['Color'], principled_node.inputs['Base Color'])
            elif texture_type == "ARM":
                sep_node = nodes.new(type='ShaderNodeSeparateRGB')
                sep_node.location = Vector((-150, offset_y - 50))
                links.new(texture_node.outputs['Color'], sep_node.inputs['Image'])
                links.new(sep_node.outputs['G'], principled_node.inputs['Roughness'])
                links.new(sep_node.outputs['B'], principled_node.inputs['Metallic'])
            elif texture_type == "Metallic" and "ARM" not in ordered_texture_files:
                links.new(texture_node.outputs['Color'], principled_node.inputs['Metallic'])
            elif texture_type == "Roughness" and "ARM" not in ordered_texture_files:
                links.new(texture_node.outputs['Color'], principled_node.inputs['Roughness'])
            elif texture_type == "Emission":
                target_input = 'Emission Color' if 'Emission Color' in principled_node.inputs else 'Emission'
                links.new(texture_node.outputs['Color'], principled_node.inputs[target_input])
                if 'Emission Strength' in principled_node.inputs:
                    principled_node.inputs['Emission Strength'].default_value = 1.0
            elif texture_type == "Normal":
                normal_map_node = nodes.new(type='ShaderNodeNormalMap')
                normal_map_node.location = Vector((-150, -600)) 
                links.new(texture_node.outputs['Color'], normal_map_node.inputs['Color'])
                links.new(normal_map_node.outputs['Normal'], principled_node.inputs['Normal'])
            elif texture_type == "Bump":
                bump_map_node = nodes.new(type='ShaderNodeBump')
                bump_map_node.location = Vector((-150, -800))
                links.new(texture_node.outputs['Color'], bump_map_node.inputs['Height'])
                if normal_map_node:
                    links.new(normal_map_node.outputs['Normal'], bump_map_node.inputs['Normal'])
                links.new(bump_map_node.outputs['Normal'], principled_node.inputs['Normal'])
            elif texture_type == "Displacement":
                disp_node = nodes.new(type='ShaderNodeDisplacement')
                disp_node.location = Vector((-50, -1000))
                links.new(texture_node.outputs['Color'], disp_node.inputs['Height'])
                links.new(disp_node.outputs['Displacement'], output_node.inputs['Displacement'])
            elif texture_type == "Alpha":
                links.new(texture_node.outputs['Color'], principled_node.inputs['Alpha'])
            
            offset_y -= 300 

    offset_y = 0
    for t_type in process_order:
        if t_type in texture_nodes:
            texture_nodes[t_type].location.y = -offset_y
            offset_y += 300

    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    tex_coord.location = Vector((-900, 0))
    mapping = nodes.new(type='ShaderNodeMapping')
    mapping.location = Vector((-700, 0))
    links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])

    for t_type in process_order:
        if t_type in texture_nodes:
            links.new(mapping.outputs['Vector'], texture_nodes[t_type].inputs['Vector'])

class ImportPBRTexturesOperator(bpy.types.Operator):
    bl_idname = "spio.import_pbr_textures"
    bl_label = "导入PBR材质 (无预览)"
    bl_description = "扫描贴图文件夹并自动构建材质，不生成场景物体"

    def execute(self, context):
        folder_path = bpy.path.abspath(context.scene.toolbox_folder_path)
        if not os.path.exists(folder_path):
            self.report({'ERROR'}, "文件夹路径无效")
            return {'CANCELLED'}
        
        recur_depth = context.scene.toolbox_recursion_depth
        valid_groups = scan_files_with_depth(
            folder_path, 
            depth=recur_depth, 
            extensions=('.png', '.jpg', '.jpeg', '.exr', '.tif', '.tga')
        )

        if not valid_groups:
            self.report({'WARNING'}, "未找到包含贴图的文件夹")
            return {'CANCELLED'}

        count = 0
        for name, files in valid_groups:
            # 检查材质是否已存在，避免覆盖，或者直接新建
            mat = bpy.data.materials.new(name=name)
            mat.use_nodes = True
            create_pbr_material(mat, files)
            count += 1
            # 注意：此处已移除 create_preview_geometry 调用

        self.report({'INFO'}, f"成功导入 {count} 个 PBR 材质到材质库")
        return {'FINISHED'}

# =============================================================================
# 功能 2：SBSAR 导入 (仅导入)
# =============================================================================

class ImportSBSAROperator(bpy.types.Operator):
    bl_idname = "spio.import_sbsar_files"
    bl_label = "导入 SBSAR (无预览)"
    bl_description = "批量导入 .sbsar 文件到材质库"

    def execute(self, context):
        if not hasattr(bpy.ops, "substance") or not hasattr(bpy.ops.substance, "ui_sbsar_load"):
            self.report({'ERROR'}, "未检测到 Adobe Substance 3D 插件")
            return {'CANCELLED'}

        folder_path = bpy.path.abspath(context.scene.toolbox_folder_path)
        if not os.path.exists(folder_path):
            self.report({'ERROR'}, "文件夹路径无效")
            return {'CANCELLED'}

        recur_depth = context.scene.toolbox_recursion_depth
        found_groups = scan_files_with_depth(
            folder_path, 
            depth=recur_depth, 
            extensions=('.sbsar')
        )

        total_files = sum(len(files) for _, files in found_groups)
        if total_files == 0:
            self.report({'WARNING'}, "未找到 .sbsar 文件")
            return {'CANCELLED'}

        for folder_name, files_in_folder in found_groups:
            if not files_in_folder: continue

            file_list_param = [{"name": os.path.basename(f)} for f in files_in_folder]
            directory = os.path.dirname(files_in_folder[0]) + os.sep

            try:
                bpy.ops.substance.ui_sbsar_load(
                    filepath=files_in_folder[0], 
                    directory=directory,         
                    files=file_list_param        
                )
            except Exception as e:
                print(f"导入文件夹 {folder_name} 时出错: {e}")
                continue
            
            # 注意：此处已移除 create_preview_geometry 调用

        self.report({'INFO'}, f"已提交导入 {total_files} 个 SBSAR 文件")
        return {'FINISHED'}

# =============================================================================
# 功能 3：新增 - 一键生成材质预览
# =============================================================================

class GeneratePreviewsOperator(bpy.types.Operator):
    bl_idname = "spio.generate_previews"
    bl_label = "为现有材质生成预览"
    bl_description = "为所有 PBR 材质生成球体预览"
    
    target_mode: bpy.props.EnumProperty(
        name="目标",
        items=[
            ('ALL', "所有材质", "处理 Blender 文件中的所有节点材质"),
            ('SELECTED', "选中物体的材质", "仅处理选中物体所使用的材质"),
        ],
        default='ALL'
    )

    def execute(self, context):
        spacing = 3.0
        start_location = context.scene.cursor.location.copy() # 从游标位置开始
        
        # 1. 收集目标材质
        materials_to_process = []
        
        if self.target_mode == 'ALL':
            # 过滤掉非节点材质（通常是 Grease Pencil 或 UI 材质）
            materials_to_process = [m for m in bpy.data.materials if m.use_nodes]
        elif self.target_mode == 'SELECTED':
            temp_set = set()
            for obj in context.selected_objects:
                if obj.type == 'MESH':
                    for slot in obj.material_slots:
                        if slot.material and slot.material.use_nodes:
                            temp_set.add(slot.material)
            materials_to_process = list(temp_set)
        
        if not materials_to_process:
            self.report({'WARNING'}, "没有找到可生成预览的 PBR 材质")
            return {'CANCELLED'}

        # 排序以保证每次生成顺序一致
        materials_to_process.sort(key=lambda m: m.name)
        
        # 2. 计算网格布局
        count = len(materials_to_process)
        grid_cols = math.ceil(math.sqrt(count))
        
        created_count = 0
        
        # 3. 生成循环
        for idx, mat in enumerate(materials_to_process):
            row = idx // grid_cols
            col = idx % grid_cols
            
            loc_x = start_location.x + (col * spacing)
            loc_y = start_location.y - (row * spacing)
            loc_z = start_location.z
            
            create_preview_geometry(mat.name, (loc_x, loc_y, loc_z), mat)
            created_count += 1
            
        self.report({'INFO'}, f"已生成 {created_count} 组材质展示球")
        return {'FINISHED'}

# =============================================================================
# 功能 4：批量材质与 UV (原有功能)
# =============================================================================

class BatchApplyMaterialUVOperator(bpy.types.Operator):
    bl_idname = "spio.batch_apply_mat_uv"
    bl_label = "应用材质与UV"
    bl_description = "为指定集合中的所有Mesh物体赋予材质并进行立方体投影UV展开"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        target_col = context.scene.batch_target_collection
        target_mat = context.scene.batch_target_material
        cube_size = context.scene.batch_cube_size

        if not target_col:
            self.report({'ERROR'}, "请先选择目标集合")
            return {'CANCELLED'}

        objects_processed = 0
        original_active = context.view_layer.objects.active
        original_selected = context.selected_objects[:]
        bpy.ops.object.select_all(action='DESELECT')

        try:
            for obj in target_col.objects:
                if obj.type == 'MESH':
                    # 1. 赋予材质
                    if target_mat:
                        obj.data.materials.clear()
                        obj.data.materials.append(target_mat)
                    
                    # 2. UV 展开
                    context.view_layer.objects.active = obj
                    obj.select_set(True)
                    
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.select_all(action='SELECT')
                    bpy.ops.uv.cube_project(cube_size=cube_size)
                    bpy.ops.object.mode_set(mode='OBJECT')
                    
                    obj.select_set(False)
                    objects_processed += 1
        except Exception as e:
            self.report({'ERROR'}, f"执行过程中出错: {str(e)}")
            if context.object and context.object.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            return {'CANCELLED'}
        
        if original_active:
            context.view_layer.objects.active = original_active
        for obj in original_selected:
            obj.select_set(True)

        msg = f"已处理 {objects_processed} 个物体"
        self.report({'INFO'}, msg)
        return {'FINISHED'}

# =============================================================================
# 面板 UI
# =============================================================================

class PBRToolboxPanel(bpy.types.Panel):
    bl_label = "PBR & SBSAR 工具箱"
    bl_idname = "PBR_TOOLBOX_PANEL"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "PBR工具"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # --- 1. 导入设置 ---
        layout.label(text="1. 资源导入 (不生成物体)", icon='IMPORT')
        box_main = layout.box()
        box_main.prop(scene, "toolbox_folder_path", text="")
        row = box_main.row()
        row.label(text="递归子文件夹:")
        row.prop(scene, "toolbox_recursion_depth", text="")
        
        col = box_main.column(align=True)
        col.operator("spio.import_pbr_textures", text="扫描并导入 PBR 贴图", icon='IMAGE_DATA')
        col.operator("spio.import_sbsar_files", text="扫描并导入 SBSAR", icon='NODE_MATERIAL')

        layout.separator()

        # --- 2. 预览生成 (新功能) ---
        layout.label(text="2. 预览生成器", icon='SPHERE')
        box_gen = layout.box()
        box_gen.label(text="为现有材质创建展示台:")
        row = box_gen.row(align=True)
        # 提供两个选项：处理所有 或 处理选中
        op_all = row.operator("spio.generate_previews", text="所有材质")
        op_all.target_mode = 'ALL'
        op_sel = row.operator("spio.generate_previews", text="仅选中物体材质")
        op_sel.target_mode = 'SELECTED'

        layout.separator()

        # --- 3. 批量场景应用 ---
        layout.label(text="3. 场景批量应用", icon='MOD_BUILD')
        box2 = layout.box()
        box2.prop(scene, "batch_target_collection", text="目标集合")
        box2.prop(scene, "batch_target_material", text="应用材质")
        
        row_uv = box2.row()
        row_uv.prop(scene, "batch_cube_size", text="UV 尺寸")
        
        op = box2.operator("spio.batch_apply_mat_uv", text="对集合应用材质&UV", icon='PLAY')

# =============================================================================
# 注册
# =============================================================================

def register():
    bpy.utils.register_class(ImportPBRTexturesOperator)
    bpy.utils.register_class(ImportSBSAROperator)
    bpy.utils.register_class(GeneratePreviewsOperator) # 新注册
    bpy.utils.register_class(BatchApplyMaterialUVOperator)
    bpy.utils.register_class(PBRToolboxPanel)
    
    # 属性注册
    bpy.types.Scene.toolbox_folder_path = bpy.props.StringProperty(
        name="资源根目录",
        description="选择包含材质或SBSAR文件的根目录",
        subtype='DIR_PATH'
    )
    
    bpy.types.Scene.toolbox_recursion_depth = bpy.props.IntProperty(
        name="递归深度",
        description="0 = 仅当前文件夹, 1 = 向下一级, 以此类推",
        default=0,
        min=0,
        max=10
    )
    
    bpy.types.Scene.batch_target_collection = bpy.props.PointerProperty(
        name="目标集合",
        type=bpy.types.Collection
    )
    bpy.types.Scene.batch_target_material = bpy.props.PointerProperty(
        name="目标材质",
        type=bpy.types.Material
    )
    bpy.types.Scene.batch_cube_size = bpy.props.FloatProperty(
        name="UV立方体尺寸",
        default=5.12,
        min=0.01
    )

def unregister():
    bpy.utils.unregister_class(ImportPBRTexturesOperator)
    bpy.utils.unregister_class(ImportSBSAROperator)
    bpy.utils.unregister_class(GeneratePreviewsOperator)
    bpy.utils.unregister_class(BatchApplyMaterialUVOperator)
    bpy.utils.unregister_class(PBRToolboxPanel)
    
    del bpy.types.Scene.toolbox_folder_path
    del bpy.types.Scene.toolbox_recursion_depth
    del bpy.types.Scene.batch_target_collection
    del bpy.types.Scene.batch_target_material
    del bpy.types.Scene.batch_cube_size

if __name__ == "__main__":
    register()