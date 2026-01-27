import { Database } from 'sql.js';
import { getDatabaseManager } from '../config/database.js';
import {
  Task,
  CreateTaskDto,
  UpdateTaskDto,
  PatchTaskDto,
} from '../schemas/task.schema.js';
import { randomUUID } from 'crypto';

interface DbRow {
  [key: string]: any;
}

interface TaskFilters {
  completed?: boolean;
  priority?: string;
  sort?: string;
  order?: string;
}

export class TaskRepository {
  private async getDb(): Promise<Database> {
    const manager = await getDatabaseManager();
    return manager.getDb();
  }

  /**
   * Convert database row to Task object (snake_case → camelCase)
   */
  private dbRowToTask(row: DbRow): Task {
    return {
      id: row.id as string,
      title: row.title as string,
      description: row.description as string | null,
      completed: row.status === 'completed',
      priority: row.priority as 'low' | 'medium' | 'high',
      dueDate: row.due_date ? new Date(row.due_date as number).toISOString() : null,
      createdAt: new Date(row.created_at as number).toISOString(),
      updatedAt: new Date(row.updated_at as number).toISOString(),
    };
  }

  /**
   * Find all tasks with optional filters
   */
  async findAll(filters?: TaskFilters): Promise<Task[]> {
    const db = await this.getDb();
    let query = 'SELECT * FROM tasks WHERE 1=1';
    const params: any[] = [];

    // Apply filters (parameterized to prevent SQL injection)
    if (filters?.completed !== undefined) {
      query += ' AND status = ?';
      params.push(filters.completed ? 'completed' : 'pending');
    }

    if (filters?.priority) {
      query += ' AND priority = ?';
      params.push(filters.priority);
    }

    // Apply sorting
    if (filters?.sort) {
      const sortColumn = filters.sort === 'createdAt'
        ? 'created_at'
        : filters.sort === 'dueDate'
        ? 'due_date'
        : filters.sort;

      const order = filters.order?.toUpperCase() === 'ASC' ? 'ASC' : 'DESC';
      query += ` ORDER BY ${sortColumn} ${order}`;
    } else {
      // Default sort by created_at DESC
      query += ' ORDER BY created_at DESC';
    }

    const stmt = db.prepare(query);
    stmt.bind(params);

    const tasks: Task[] = [];
    while (stmt.step()) {
      const row = stmt.getAsObject();
      tasks.push(this.dbRowToTask(row));
    }
    stmt.free();

    return tasks;
  }

  /**
   * Find task by ID
   */
  async findById(id: string): Promise<Task | null> {
    const db = await this.getDb();
    const stmt = db.prepare('SELECT * FROM tasks WHERE id = ?');
    stmt.bind([id]);

    if (stmt.step()) {
      const row = stmt.getAsObject();
      stmt.free();
      return this.dbRowToTask(row);
    }

    stmt.free();
    return null;
  }

  /**
   * Create new task
   */
  async create(data: CreateTaskDto): Promise<Task> {
    const db = await this.getDb();
    const now = Date.now();
    const id = randomUUID();

    const status = data.completed ? 'completed' : 'pending';
    const priority = data.priority || 'medium';
    const description = data.description ?? null;
    const dueDate = data.dueDate ? new Date(data.dueDate).getTime() : null;

    const stmt = db.prepare(`
      INSERT INTO tasks (id, title, description, status, priority, created_at, updated_at, due_date)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `);

    stmt.bind([
      id,
      data.title,
      description,
      status,
      priority,
      now,
      now,
      dueDate,
    ]);

    stmt.step();
    stmt.free();

    // Save database to file
    const manager = await getDatabaseManager();
    await manager.saveToFile();

    return {
      id,
      title: data.title,
      description,
      completed: data.completed || false,
      priority: priority as 'low' | 'medium' | 'high',
      dueDate: data.dueDate || null,
      createdAt: new Date(now).toISOString(),
      updatedAt: new Date(now).toISOString(),
    };
  }

  /**
   * Update task (full update)
   */
  async update(id: string, data: UpdateTaskDto): Promise<Task | null> {
    const db = await this.getDb();
    const existing = await this.findById(id);

    if (!existing) {
      return null;
    }

    const now = Date.now();
    const status = data.completed ? 'completed' : 'pending';
    const dueDate = data.dueDate ? new Date(data.dueDate).getTime() : null;

    const stmt = db.prepare(`
      UPDATE tasks
      SET title = ?, description = ?, status = ?, priority = ?, updated_at = ?, due_date = ?
      WHERE id = ?
    `);

    stmt.bind([
      data.title,
      data.description,
      status,
      data.priority,
      now,
      dueDate,
      id,
    ]);

    stmt.step();
    stmt.free();

    // Save database to file
    const manager = await getDatabaseManager();
    await manager.saveToFile();

    return {
      id,
      title: data.title,
      description: data.description,
      completed: data.completed,
      priority: data.priority,
      dueDate: data.dueDate,
      createdAt: existing.createdAt,
      updatedAt: new Date(now).toISOString(),
    };
  }

  /**
   * Patch task (partial update)
   */
  async patch(id: string, data: PatchTaskDto): Promise<Task | null> {
    const db = await this.getDb();
    const existing = await this.findById(id);

    if (!existing) {
      return null;
    }

    const now = Date.now();
    const updates: string[] = [];
    const params: any[] = [];

    if (data.title !== undefined) {
      updates.push('title = ?');
      params.push(data.title);
    }

    if (data.description !== undefined) {
      updates.push('description = ?');
      params.push(data.description);
    }

    if (data.completed !== undefined) {
      updates.push('status = ?');
      params.push(data.completed ? 'completed' : 'pending');
    }

    if (data.priority !== undefined) {
      updates.push('priority = ?');
      params.push(data.priority);
    }

    if (data.dueDate !== undefined) {
      updates.push('due_date = ?');
      params.push(data.dueDate ? new Date(data.dueDate).getTime() : null);
    }

    if (updates.length === 0) {
      return existing;
    }

    updates.push('updated_at = ?');
    params.push(now);
    params.push(id);

    const query = `UPDATE tasks SET ${updates.join(', ')} WHERE id = ?`;
    const stmt = db.prepare(query);
    stmt.bind(params);
    stmt.step();
    stmt.free();

    // Save database to file
    const manager = await getDatabaseManager();
    await manager.saveToFile();

    // Return updated task
    return await this.findById(id);
  }

  /**
   * Delete task
   */
  async delete(id: string): Promise<boolean> {
    const db = await this.getDb();
    const existing = await this.findById(id);

    if (!existing) {
      return false;
    }

    const stmt = db.prepare('DELETE FROM tasks WHERE id = ?');
    stmt.bind([id]);
    stmt.step();
    stmt.free();

    // Save database to file
    const manager = await getDatabaseManager();
    await manager.saveToFile();

    return true;
  }
}

export const taskRepository = new TaskRepository();
