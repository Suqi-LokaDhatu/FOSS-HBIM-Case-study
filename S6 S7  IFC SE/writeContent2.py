import ifcopenshell
import ifcopenshell.util.element
from datetime import datetime

def add_properties_by_globalid(ifc_file_path, global_ids, properties_to_add, output_file_path=None):
    """
    通过GlobalId查找实体并添加属性
    
    参数:
        ifc_file_path (str): 输入的IFC文件路径
        global_ids (list): 要查找的GlobalId列表
        properties_to_add (dict): 要添加的属性字典，格式为{"属性集名称": {"属性名": "属性值"}}
        output_file_path (str): 输出的IFC文件路径(可选，默认为输入文件添加"_modified"后缀)
    
    返回:
        dict: 操作结果，包含成功和失败的信息
    """
    
    # 设置输出文件路径
    if output_file_path is None:
        if ifc_file_path.endswith('.ifc'):
            output_file_path = ifc_file_path.replace('.ifc', '_modified.ifc')
        else:
            output_file_path = ifc_file_path + '_modified.ifc'
    
    result = {
        "success": False,
        "message": "",
        "found_entities": [],
        "not_found_ids": [],
        "processed_entities": []
    }
    
    try:
        # 1. 打开IFC文件
        print(f"正在打开IFC文件: {ifc_file_path}")
        ifc_file = ifcopenshell.open(ifc_file_path)
        print(f"成功打开文件，IFC架构: {ifc_file.schema}")
        
        # 2. 通过GlobalId查找实体
        found_entities = []
        not_found_ids = []
        
        for global_id in global_ids:
            try:
                entity = ifc_file.by_guid(global_id)
                if entity:
                    found_entities.append(entity)
                    result["found_entities"].append({
                        "global_id": global_id,
                        "type": entity.is_a(),
                        "name": getattr(entity, "Name", "Unnamed")
                    })
                else:
                    not_found_ids.append(global_id)
                    result["not_found_ids"].append(global_id)
            except Exception as e:
                print(f"查找GlobalId {global_id} 时出错: {str(e)}")
                not_found_ids.append(global_id)
                result["not_found_ids"].append(global_id)
        
        if not found_entities:
            result["message"] = "未找到任何匹配的实体"
            return result
        
        print(f"找到 {len(found_entities)} 个匹配的实体，{len(not_found_ids)} 个未找到")
        
        # 3. 获取或创建所有者历史记录
        owner_history = get_or_create_owner_history(ifc_file)
        if not owner_history:
            result["message"] = "无法创建所有者历史记录"
            return result
        
        # 4. 为每个找到的实体添加属性
        processed_entities = []

        if(len(found_entities) == len(properties_to_add)):
            for entity in found_entities:
                index = found_entities.index(entity)
                success = add_properties_to_element(ifc_file, entity, properties_to_add[index], owner_history)
                processed_entities.append({
                    "global_id": entity.GlobalId,
                    "type": entity.is_a(),
                    "name": getattr(entity, "Name", "Unnamed"),
                    "success": success
                })
                result["processed_entities"].append({
                    "global_id": entity.GlobalId,
                    "type": entity.is_a(),
                    "name": getattr(entity, "Name", "Unnamed"),
                    "success": success
                })
        
        # 5. 保存修改后的文件
        print(f"正在保存修改后的文件: {output_file_path}")
        ifc_file.write(output_file_path)
        print("文件保存成功!")
        
        result["success"] = True
        result["message"] = f"成功处理 {len([e for e in processed_entities if e['success']])} 个实体"
        
        return result
        
    except Exception as e:
        error_msg = f"处理过程中发生错误: {str(e)}"
        print(error_msg)
        result["message"] = error_msg
        return result

def get_or_create_owner_history(ifc_file):
    """
    获取或创建所有者历史记录
    
    参数:
        ifc_file: IFC文件对象
    
    返回:
        owner_history: 所有者历史记录对象
    """
    try:
        # 尝试获取现有的所有者历史记录
        owner_histories = ifc_file.by_type("IfcOwnerHistory")
        if owner_histories:
            return owner_histories[0]
        
        # 如果没有找到，创建一个新的
        print("创建新的所有者历史记录...")
        
        # 创建组织和人员
        organization = ifc_file.createIfcOrganization()
        organization.Name = "Property Editor"
        organization.Description = "Automated Property Editor"
        
        person = ifc_file.createIfcPerson()
        person.GivenName = "System"
        person.FamilyName = "Admin"
        
        person_and_org = ifc_file.createIfcPersonAndOrganization(person, organization)
        
        # 创建应用程序
        application = ifc_file.createIfcApplication()
        application.ApplicationDeveloper = organization
        application.Version = "1.0"
        application.ApplicationFullName = "IFC Property Editor"
        application.ApplicationIdentifier = "IFCPropertyEditor"
        
        # 创建所有者历史记录
        owner_history = ifc_file.createIfcOwnerHistory()
        owner_history.OwningUser = person_and_org
        owner_history.OwningApplication = application
        owner_history.ChangeAction = "ADDED"
        owner_history.CreationDate = int(datetime.now().timestamp())
        
        return owner_history
        
    except Exception as e:
        print(f"创建所有者历史记录时出错: {str(e)}")
        return None

def add_properties_to_element(ifc_file, element, properties_to_add, owner_history):
    """
    为指定元素添加属性
    
    参数:
        ifc_file: IFC文件对象
        element: 要添加属性的元素
        properties_to_add (dict): 要添加的属性字典
        owner_history: 所有者历史记录对象
    
    返回:
        bool: 操作是否成功
    """
    try:
        # 获取元素的现有属性集
        existing_psets = ifcopenshell.util.element.get_psets(element)
        
        for pset_name, properties in properties_to_add.items():
            # 检查属性集是否已存在
            if pset_name in existing_psets:
                print(f"元素 {getattr(element, 'Name', 'Unnamed')} 已存在属性集 '{pset_name}'，跳过添加")
                continue
            
            # 创建属性集
            property_set = create_property_set(ifc_file, pset_name, properties, owner_history)
            
            if property_set:
                # 将属性集与元素关联
                create_rel_defines_by_properties(ifc_file, element, property_set, owner_history)
                print(f"已为元素 {getattr(element, 'Name', 'Unnamed')} 添加属性集 '{pset_name}'")
        
        return True
                
    except Exception as e:
        print(f"为元素 {getattr(element, 'Name', 'Unnamed')} 添加属性时出错: {str(e)}")
        return False

def create_property_set(ifc_file, pset_name, properties, owner_history):
    """
    创建属性集
    
    参数:
        ifc_file: IFC文件对象
        pset_name (str): 属性集名称
        properties (dict): 属性字典
        owner_history: 所有者历史记录对象
    
    返回:
        property_set: 创建的属性集对象
    """
    try:
        # 创建属性列表
        property_objects = []
        
        for prop_name, prop_value in properties.items():
            # 根据值的类型创建适当的属性
            if isinstance(prop_value, int):
                prop = ifc_file.createIfcPropertySingleValue(
                    prop_name, None, 
                    ifc_file.createIfcInteger(prop_value), None
                )
            elif isinstance(prop_value, float):
                prop = ifc_file.createIfcPropertySingleValue(
                    prop_name, None, 
                    ifc_file.createIfcReal(prop_value), None
                )
            elif isinstance(prop_value, bool):
                prop = ifc_file.createIfcPropertySingleValue(
                    prop_name, None, 
                    ifc_file.createIfcBoolean(prop_value), None
                )
            else:
                # 默认为文本值
                prop = ifc_file.createIfcPropertySingleValue(
                    prop_name, None, 
                    ifc_file.createIfcText(str(prop_value)), None
                )
            property_objects.append(prop)
        
        # 创建属性集
        property_set = ifc_file.createIfcPropertySet(
            ifcopenshell.guid.new(),
            owner_history,
            pset_name,
            None,
            property_objects
        )
        
        return property_set
        
    except Exception as e:
        print(f"创建属性集 '{pset_name}' 时出错: {str(e)}")
        return None

def create_rel_defines_by_properties(ifc_file, element, property_set, owner_history):
    """
    创建属性定义关系
    
    参数:
        ifc_file: IFC文件对象
        element: 要关联的元素
        property_set: 属性集对象
        owner_history: 所有者历史记录对象
    """
    try:
        # 查找现有的关系
        existing_relations = ifc_file.by_type("IfcRelDefinesByProperties")
        
        # 检查是否已存在关联此属性集的关系
        for rel in existing_relations:
            if rel.RelatingPropertyDefinition == property_set:
                # 如果已存在，只需将元素添加到关系中
                related_objects = list(rel.RelatedObjects)
                if element not in related_objects:
                    related_objects.append(element)
                    rel.RelatedObjects = related_objects
                return
        
        # 如果没有现有关系，创建新的
        ifc_file.createIfcRelDefinesByProperties(
            ifcopenshell.guid.new(),
            owner_history,
            None,
            None,
            [element],
            property_set
        )
        
    except Exception as e:
        print(f"创建属性定义关系时出错: {str(e)}")

# 用法
if __name__ == "__main__":

    you_ifc_file = "example.ifc"
    
    # 定义要查找的GlobalId列表
    target_global_ids = [
        "1b92i2u2PF7uQ2iY9NgvMw",  # 替换为实际的GlobalId 窗001
        "0wDloALsT9pQy_R_wnk4lr",  #门
        "1b92i2u2PF7uQ2iY9NgvMw",  #窗
        "1SbsBZFH51LvM9bYA3nYym",  #房顶建筑
        "0BAkZJwODF5ADiw_kAsmaF",  #墙
        "0$LW1NMf1FlB9v4QDuVq$x",  #屋顶
        "1vhqqCDuf4vPLPEQNyMGaS",  #雕塑
        "1xWiAm9LPBaQkCh988iKIn",  #雕塑
        "13zbGMafH8Ah0XOP518f8g",  #雕塑	

    ]
    
    # 定义要添加的属性
    custom_properties = [{
        "DynamicData": {
            "DoorWidth": "50 mm",
            "Fillet": "40 mm",
            "Height": "1000 mm",
            "Rise": "300 mm",
            "Sill": "3000 mm",
            "SillHeight": "20 mm",
            "Thichness": "120 mm",
            "Width": "1000 mm",
        },
        "OtherInfo": {
            "Data": "2024-01-01",
        }
    },
        {
        "DynamicData": {
            "BottomOffset": "100 mm",
            "DoorWidth": "50 mm",
            "Height": "2500 mm",
            "SillHight": "300 mm",
            "Thichness": "120 mm",
            "TopHight": "500 mm",
            "Width": "1200 mm"
        },
         "OtherInfo": {
            "Data": "2024-01-01",
        }
    },
    {
        "DynamicData": {
            "DoorWidth": "50 mm",
            "Fillet": "40 mm",
            "Height": "3000 mm",
            "Rise": "1000 mm",
            "Sill": "3000 mm",
            "SillHeight": "20 mm",
            "Thichness": "120 mm",
            "Width": "2000 mm"
        },
        "OtherInfo": {
            "Data": "2024-01-01",
        }
    },
    {
        "DynamicData": {
            "Height": "3000 mm",
            "Width": "2000 mm"
        },
        "OtherInfo": {
            "Data": "2024-01-01",
        }
    },
    {
        "DynamicData": {
            "BuildingLength": "7390 mm",
            "BuildingWidth": "6140 mm",
            "EavesOverhang": "800 mm",
            "FloorLevel": "100 mm",
            "RoofRatio": 0.8,
            "WallHeight":"8160 mm",
            "WallHeight1":"7680 mm",
            "WallThickness":"100 mm"
        },
        "OtherInfo": {
            "Data": "2024-01-01",
        }
    },
    {
        "DynamicData": {
            "Perimetric": "800 mm",
            "RoofHeight": "2000 mm",
            "RoofThickness": "100 mm"
        },
        "OtherInfo": {
            "Data": "2024-01-01",
        }
    },
{
        "DynamicData": {
            "Height": "3000 mm",
            "Width": "500 mm"
        },
        "OtherInfo": {
            "Data": "2024-01-01",
        }
    },
{
        "DynamicData": {
            "Height": "3000 mm",
            "Width": "500 mm"
        },
        "OtherInfo": {
            "Data": "2024-01-01",
        }
    },
{
        "DynamicData": {
            "Height": "3000 mm",
            "Width": "500 mm"
        },
        "OtherInfo": {
            "Data": "2024-01-01",
        }
    }
    ]
    
    # 调用函数
    result = add_properties_by_globalid(
        ifc_file_path="Allcontent.ifc",  # 替换为你的IFC文件路径
        global_ids=target_global_ids,
        properties_to_add=custom_properties,
        output_file_path="Allcontent_modified.ifc"  # 可选，指定输出文件路径
    )

