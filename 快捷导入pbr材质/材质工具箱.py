bl_info = {
    "name": "PBR工具箱 (导入 + 批量UV)",
    "author": "380kkm (Modified by Gemini)",
    "version": (1, 5),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > PBR工具",
    "description": "包含PBR快捷导入和集合物体批量材质UV赋予",
    "category": "3D View"
}

import bpy
import os
from mathutils import Vector
import math

# =============================================================================
# 第一部分：PBR 导入功能 (核心逻辑保持不变)
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
    bl_label = "导入PBR材质(球+板)"

    def execute(self, context):
        folder_path = bpy.path.abspath(context.scene.pbr_folder_path)
        if not os.path.exists(folder_path):
            self.report({'ERROR'}, "文件夹路径无效")
            return {'CANCELLED'}
        
        valid_subfolders = []
        for subfolder_name in os.listdir(folder_path):
            subfolder_path = os.path.join(folder_path, subfolder_name)
            if os.path.isdir(subfolder_path):
                texture_files = [os.path.join(subfolder_path, f) for f in os.listdir(subfolder_path)
                                 if f.lower().endswith(('.png', '.jpg', '.jpeg', '.exr', '.tif', '.tga'))]
                if texture_files:
                    valid_subfolders.append((subfolder_name, texture_files))

        if not valid_subfolders:
            self.report({'WARNING'}, "未找到包含贴图的子文件夹")
            return {'CANCELLED'}

        spacing = 3.0
        grid_cols = math.ceil(math.sqrt(len(valid_subfolders)))

        for idx, (name, files) in enumerate(valid_subfolders):
            row = idx // grid_cols
            col = idx % grid_cols
            loc_x = col * spacing
            loc_y = -row * spacing
            
            mat = bpy.data.materials.new(name=name)
            mat.use_nodes = True
            create_pbr_material(mat, files)

            bpy.ops.mesh.primitive_plane_add(size=2.0, location=(loc_x, loc_y, 0))
            bpy.context.active_object.name = f"{name}_Plane"
            bpy.context.active_object.data.materials.append(mat)

            bpy.ops.mesh.primitive_uv_sphere_add(radius=0.6, location=(loc_x, loc_y, 0.6))
            bpy.context.active_object.name = f"{name}_Sphere"
            bpy.ops.object.shade_smooth()
            bpy.context.active_object.data.materials.append(mat)

        self.report({'INFO'}, f"成功导入 {len(valid_subfolders)} 组材质")
        return {'FINISHED'}

# =============================================================================
# 第二部分：批量应用材质与UV (新功能)
# =============================================================================

class BatchApplyMaterialUVOperator(bpy.types.Operator):
    bl_idname = "spio.batch_apply_mat_uv"
    bl_label = "应用材质与UV"
    bl_description = "为指定集合中的所有Mesh物体赋予材质并进行立方体投影UV展开"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # 获取用户选择的集合和材质
        target_col = context.scene.batch_target_collection
        target_mat = context.scene.batch_target_material
        cube_size = context.scene.batch_cube_size

        if not target_col:
            self.report({'ERROR'}, "请先选择目标集合")
            return {'CANCELLED'}

        # 处理材质逻辑
        mat_to_apply = None
        if target_mat:
            mat_to_apply = target_mat
        else:
            # 如果没选材质，给一个提示或创建一个空材质
            self.report({'WARNING'}, "未选择材质，将仅进行UV展开")
        
        objects_processed = 0

        # 为了避免上下文问题，先保存当前选中状态
        original_active = context.view_layer.objects.active
        original_selected = context.selected_objects[:]
        bpy.ops.object.select_all(action='DESELECT')

        try:
            for obj in target_col.objects:
                if obj.type == 'MESH':
                    # 1. 赋予材质
                    if mat_to_apply:
                        obj.data.materials.clear()
                        obj.data.materials.append(mat_to_apply)
                    
                    # 2. UV 展开
                    context.view_layer.objects.active = obj
                    obj.select_set(True)
                    
                    # 切换到编辑模式
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.select_all(action='SELECT')
                    # 执行立方体投影
                    bpy.ops.uv.cube_project(cube_size=cube_size)
                    # 回到物体模式
                    bpy.ops.object.mode_set(mode='OBJECT')
                    
                    obj.select_set(False)
                    objects_processed += 1
        except Exception as e:
            self.report({'ERROR'}, f"执行过程中出错: {str(e)}")
            # 尝试恢复模式
            if context.object and context.object.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            return {'CANCELLED'}
        
        # 恢复原来的选中状态
        if original_active:
            context.view_layer.objects.active = original_active
        for obj in original_selected:
            obj.select_set(True)

        msg = f"已处理 {objects_processed} 个物体 (集合: {target_col.name})"
        if mat_to_apply:
            msg += f" | 材质: {mat_to_apply.name}"
        
        self.report({'INFO'}, msg)
        return {'FINISHED'}

# =============================================================================
# 面板与注册
# =============================================================================

class PBRToolboxPanel(bpy.types.Panel):
    bl_label = "PBR 工具箱"
    bl_idname = "PBR_TOOLBOX_PANEL"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "PBR工具"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # --- 部分 1: PBR 导入 ---
        layout.label(text="PBR 批量导入", icon='IMPORT')
        box1 = layout.box()
        box1.prop(scene, "pbr_folder_path", text="")
        box1.operator("spio.import_pbr_textures", text="扫描文件夹并导入", icon='FILE_FOLDER')

        layout.separator()

        # --- 部分 2: 批量材质与UV ---
        layout.label(text="批量 材质 & UV", icon='MOD_BUILD')
        box2 = layout.box()
        
        # 使用 PointerProperty 自动获得搜索框
        box2.prop(scene, "batch_target_collection", text="目标集合")
        box2.prop(scene, "batch_target_material", text="目标材质")
        
        row = box2.row()
        row.prop(scene, "batch_cube_size", text="UV 尺寸")
        
        # 按钮
        op = box2.operator("spio.batch_apply_mat_uv", text="执行批量应用", icon='PLAY')


def register():
    # 注册类
    bpy.utils.register_class(ImportPBRTexturesOperator)
    bpy.utils.register_class(BatchApplyMaterialUVOperator)
    bpy.utils.register_class(PBRToolboxPanel)
    
    # 注册属性
    bpy.types.Scene.pbr_folder_path = bpy.props.StringProperty(
        name="贴图路径",
        description="选择包含PBR贴图子文件夹的根目录",
        subtype='DIR_PATH'
    )
    
    # 新增属性：使用 PointerProperty 实现搜索功能
    bpy.types.Scene.batch_target_collection = bpy.props.PointerProperty(
        name="目标集合",
        type=bpy.types.Collection,
        description="选择要处理的集合"
    )
    bpy.types.Scene.batch_target_material = bpy.props.PointerProperty(
        name="目标材质",
        type=bpy.types.Material,
        description="选择要统一赋予的材质（留空则只做UV）"
    )
    bpy.types.Scene.batch_cube_size = bpy.props.FloatProperty(
        name="UV立方体尺寸",
        default=5.12,
        min=0.01,
        description="立方体投影的尺寸参数"
    )

def unregister():
    bpy.utils.unregister_class(ImportPBRTexturesOperator)
    bpy.utils.unregister_class(BatchApplyMaterialUVOperator)
    bpy.utils.unregister_class(PBRToolboxPanel)
    
    del bpy.types.Scene.pbr_folder_path
    del bpy.types.Scene.batch_target_collection
    del bpy.types.Scene.batch_target_material
    del bpy.types.Scene.batch_cube_size

if __name__ == "__main__":
    register()