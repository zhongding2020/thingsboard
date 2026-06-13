# 原始数据查询页面 技术设计

## 背景

当前系统支持通过条码精确查询单条工艺参数+检测记录，但缺少浏览和筛选所有已上传原始数据的功能。需要一个列表页面展示已入库的原始数据，支持按条码、设备、时间范围筛选。

## 设计目标

- 列表展示所有已入库的工艺参数+检测记录，支持分页
- 通过条码（精确）、设备类型、处理时间范围筛选
- 点击展开查看 params 和 results 的键值对明细
- 新增独立「原始数据」页面，侧边栏导航

## 数据库

直接使用已有 `analysis_view`，无需 DDL 变更：

```sql
CREATE OR REPLACE VIEW analysis_view AS
SELECT p.barcode, p.device_id, p.processed_at, p.params,
       i.station_id, i.inspected_at, i.results
FROM process_summary p
LEFT JOIN inspection_results i ON i.barcode = p.barcode;
```

## 后端设计

### Repository 层

在 `DataRepository` 中新增方法 `query_records`：

```python
async def query_records(
    self,
    barcode: str | None = None,
    device_id: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
```

SQL 使用动态 WHERE 拼接（参数化查询防注入），加 `OFFSET/LIMIT` 分页，`COUNT(*) OVER()` 获取总数避免两次查询。

### API 层

```
GET /api/v1/analysis/records
  Query:
    barcode      str?     条码精确匹配
    device_id    str?     设备类型
    start_time   datetime? 处理时间起始
    end_time     datetime? 处理时间截止
    page         int      default=1
    page_size    int      default=20, max=100
  Response 200:
    { items: AnalysisRecord[], total: int, page: int, page_size: int }
```

`AnalysisRecord` 即 `analysis_view` 的完整行（barcode, device_id, processed_at, params, station_id, inspected_at, results）。

### 设备列表辅助接口

前端需要设备类型的下拉选项，新增轻量接口：

```
GET /api/v1/analysis/devices
  Response 200: [{ device_id: "reflow-oven" }, { device_id: "injection-molder" }]
```

从 `process_summary` 表 `SELECT DISTINCT device_id ORDER BY device_id`。

## 前端设计

### 路由与导航

- 路由：`/data` → `DataView.vue`
- 侧边栏现有菜单项后追加「原始数据」项，图标 `el-icon-document-copy`

### API 层

新增 `web/src/api/records.ts`：

```typescript
export function queryRecords(params: RecordsQuery): Promise<RecordsResponse>
export function listDevices(): Promise<{device_id: string}[]>
```

### DataView.vue

#### 筛选栏

顶部一行，三个筛选控件+查询按钮：

| 控件 | 类型 | 绑定 |
|------|------|------|
| 条码 | el-input，精确匹配 | barcode |
| 设备 | el-select，选项来自 `/api/v1/analysis/devices` | device_id |
| 时间范围 | el-date-picker type="datetimerange" | [start_time, end_time] |

「查询」按钮触发重新加载。

#### 表格

使用 `el-table` 的 expandable row 模式：

摘要列：

| 列 | 内容 |
|----|------|
| barcode | 条码 |
| device_id | 设备 |
| processed_at | 处理时间 |
| inspected_at | 检测时间 |
| 参数数 | params 的 key 数量（前端计算） |
| 结果 | 全部 pass → 绿色 `el-tag type="success"`=pass；有 fail → 红色 `el-tag type="danger"`=fail；无检测记录 → `—` |

展开行展示两个 `el-descriptions` 卡片：

1. **工艺参数**：遍历 params JSON，每行 `param_key | param_value`
2. **检测结果**：遍历 results JSON，每行 `result_key | result_value` + 结果标签

#### 分页

`el-pagination` 置于表格下方，每页 20 条，显示总数。

### 空状态与加载

- 无数据时显示 `el-empty` 空状态提示
- 加载中表格显示骨架屏或 loading 指示
- 筛选后无结果提示「未找到匹配记录」

## 非目标

- 不提供数据导出功能
- 不提供批量操作（删除/编辑）
- 不排序（按 processed_at 降序固定）
- 不做 params/results 的 JSON 值类型渲染（统一显示 toString）

## 实现文件

```text
src/process_opt/common/repositories.py  # +query_records
src/process_opt/api/app.py              # +records 路由, +devices 路由
tests/common/test_repositories.py       # +query_records 测试
tests/api/test_app.py                   # +records 路由测试
web/src/api/records.ts                  # 新增
web/src/views/DataView.vue              # 新增
web/src/router/index.ts                 # +/data 路由
web/src/components/AppLayout.vue        # +侧边栏菜单项
```

## 测试

- Repository: 验证 WHERE 条件拼接正确、分页正常、总数正确
- API: 验证各筛选参数组合、分页边界
- 前端: 无状态逻辑，不写前端测试
