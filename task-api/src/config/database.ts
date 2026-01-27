import initSqlJs, { Database, SqlJsStatic } from 'sql.js';
import fs from 'fs/promises';
import path from 'path';
import { env } from './env.js';

export class DatabaseManager {
  private db: Database | null = null;
  private SQL: SqlJsStatic | null = null;
  private dbPath: string;

  constructor(dbPath: string = env.DATABASE_PATH) {
    this.dbPath = dbPath;
  }

  /**
   * Initialize sql.js with WebAssembly and load/create database
   */
  async initialize(): Promise<void> {
    // Initialize sql.js with local WASM file
    const wasmPath = path.join(
      path.dirname(new URL(import.meta.url).pathname),
      '../../node_modules/sql.js/dist/sql-wasm.wasm'
    );
    this.SQL = await initSqlJs({
      locateFile: (file: string) => {
        if (file.endsWith('.wasm')) {
          return wasmPath;
        }
        return file;
      },
    });

    // Ensure data directory exists
    const dataDir = path.dirname(this.dbPath);
    try {
      await fs.mkdir(dataDir, { recursive: true });
    } catch (error) {
      // Directory might already exist
    }

    // Load existing database or create new one
    try {
      const buffer = await fs.readFile(this.dbPath);
      this.db = new this.SQL.Database(new Uint8Array(buffer));
      console.log(`Database loaded from ${this.dbPath}`);
    } catch (error) {
      // Create new database if file doesn't exist
      this.db = new this.SQL.Database();
      console.log('Created new database');
    }

    // Run migrations
    await this.runMigrations();
  }

  /**
   * Run database migrations
   */
  private async runMigrations(): Promise<void> {
    if (!this.db) {
      throw new Error('Database not initialized');
    }

    // Create tasks table
    this.db.run(`
      CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        priority TEXT NOT NULL DEFAULT 'medium',
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL,
        due_date INTEGER
      )
    `);

    // Create indexes
    this.db.run('CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)');
    this.db.run('CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority)');
    this.db.run('CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at)');
    this.db.run('CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date)');

    console.log('Database migrations completed');
  }

  /**
   * Get the database instance
   */
  getDb(): Database {
    if (!this.db) {
      throw new Error('Database not initialized. Call initialize() first.');
    }
    return this.db;
  }

  /**
   * Save the database to file
   */
  async saveToFile(): Promise<void> {
    if (!this.db) {
      throw new Error('Database not initialized');
    }

    const data = this.db.export();
    const buffer = Buffer.from(data);
    await fs.writeFile(this.dbPath, buffer);
  }

  /**
   * Close the database connection
   */
  async close(): Promise<void> {
    if (this.db) {
      await this.saveToFile();
      this.db.close();
      this.db = null;
      console.log('Database connection closed');
    }
  }
}

// Singleton instance
let dbManager: DatabaseManager | null = null;

/**
 * Get or create the database manager singleton
 */
export async function getDatabaseManager(): Promise<DatabaseManager> {
  if (!dbManager) {
    dbManager = new DatabaseManager();
    await dbManager.initialize();
  }
  return dbManager;
}

/**
 * Close the database manager singleton
 */
export async function closeDatabaseManager(): Promise<void> {
  if (dbManager) {
    await dbManager.close();
    dbManager = null;
  }
}
