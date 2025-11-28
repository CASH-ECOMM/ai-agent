import os
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Database connection configuration
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5555")
PG_USER = os.getenv("PG_USER", "dev")
PG_PASSWORD = os.getenv("PG_PASSWORD", "dev")

# List of databases to query
DATABASES = ["catalogue_db", "auction_db", "payment_db"]


def get_connection(database):
    """Create a connection to a specific database."""
    try:
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            database=database,
            user=PG_USER,
            password=PG_PASSWORD,
        )
        return conn
    except Exception as e:
        print(f"Error connecting to {database}: {e}")
        return None


def get_tables(conn):
    """Get all tables in the current database."""
    query = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """
    cursor = conn.cursor()
    cursor.execute(query)
    tables = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return tables


def get_table_schema(conn, table_name):
    """Get the schema for a specific table."""
    query = """
        SELECT 
            column_name,
            data_type,
            character_maximum_length,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_schema = 'public' 
        AND table_name = %s
        ORDER BY ordinal_position;
    """
    cursor = conn.cursor()
    cursor.execute(query, (table_name,))
    columns = cursor.fetchall()
    cursor.close()
    return columns


def get_constraints(conn, table_name):
    """Get constraints for a specific table."""
    query = """
        SELECT 
            tc.constraint_name,
            tc.constraint_type,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        LEFT JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        LEFT JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.table_schema = 'public'
        AND tc.table_name = %s
        ORDER BY tc.constraint_type, tc.constraint_name;
    """
    cursor = conn.cursor()
    cursor.execute(query, (table_name,))
    constraints = cursor.fetchall()
    cursor.close()
    return constraints


def get_indexes(conn, table_name):
    """Get indexes for a specific table."""
    query = """
        SELECT 
            indexname,
            indexdef
        FROM pg_indexes
        WHERE schemaname = 'public'
        AND tablename = %s
        ORDER BY indexname;
    """
    cursor = conn.cursor()
    cursor.execute(query, (table_name,))
    indexes = cursor.fetchall()
    cursor.close()
    return indexes


def format_schema_info(database_name, tables_info):
    """Format the schema information into a readable string."""
    output = []
    output.append("=" * 80)
    output.append(f"DATABASE: {database_name}")
    output.append("=" * 80)
    output.append("")

    if not tables_info:
        output.append("No tables found in this database.")
        output.append("")
        return "\n".join(output)

    for table_name, schema_info in tables_info.items():
        output.append("-" * 80)
        output.append(f"TABLE: {table_name}")
        output.append("-" * 80)
        output.append("")

        # Columns
        output.append("COLUMNS:")
        for col in schema_info["columns"]:
            col_name, data_type, max_length, nullable, default = col
            type_info = data_type
            if max_length:
                type_info += f"({max_length})"
            nullable_str = "NULL" if nullable == "YES" else "NOT NULL"
            default_str = f" DEFAULT {default}" if default else ""
            output.append(f"  - {col_name}: {type_info} {nullable_str}{default_str}")
        output.append("")

        # Constraints
        if schema_info["constraints"]:
            output.append("CONSTRAINTS:")
            for constraint in schema_info["constraints"]:
                (
                    constraint_name,
                    constraint_type,
                    column_name,
                    foreign_table,
                    foreign_column,
                ) = constraint
                if constraint_type == "PRIMARY KEY":
                    output.append(
                        f"  - PRIMARY KEY: {column_name} (constraint: {constraint_name})"
                    )
                elif constraint_type == "FOREIGN KEY":
                    output.append(
                        f"  - FOREIGN KEY: {column_name} -> {foreign_table}({foreign_column}) (constraint: {constraint_name})"
                    )
                elif constraint_type == "UNIQUE":
                    output.append(
                        f"  - UNIQUE: {column_name} (constraint: {constraint_name})"
                    )
                elif constraint_type == "CHECK":
                    output.append(
                        f"  - CHECK: {column_name} (constraint: {constraint_name})"
                    )
            output.append("")

        # Indexes
        if schema_info["indexes"]:
            output.append("INDEXES:")
            for index in schema_info["indexes"]:
                index_name, index_def = index
                output.append(f"  - {index_name}")
                output.append(f"    {index_def}")
            output.append("")

        output.append("")

    return "\n".join(output)


def collect_all_database_schemas():
    """Collect schemas from all databases and write to a file."""
    output_file = os.path.join(os.path.dirname(__file__), "database_schemas.txt")

    all_output = []
    all_output.append("=" * 80)
    all_output.append("DATABASE SCHEMAS COLLECTION")
    all_output.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    all_output.append("=" * 80)
    all_output.append("")
    all_output.append("")

    for database in DATABASES:
        print(f"Collecting schema information from {database}...")
        conn = get_connection(database)

        if not conn:
            all_output.append(f"Failed to connect to {database}")
            all_output.append("")
            continue

        try:
            tables = get_tables(conn)
            tables_info = {}

            for table in tables:
                print(f"  Processing table: {table}")
                tables_info[table] = {
                    "columns": get_table_schema(conn, table),
                    "constraints": get_constraints(conn, table),
                    "indexes": get_indexes(conn, table),
                }

            schema_output = format_schema_info(database, tables_info)
            all_output.append(schema_output)
            all_output.append("")

        except Exception as e:
            print(f"Error processing {database}: {e}")
            all_output.append(f"Error processing {database}: {e}")
            all_output.append("")
        finally:
            conn.close()

    # Write to file
    with open(output_file, "w") as f:
        f.write("\n".join(all_output))

    print(f"\nSchema information saved to: {output_file}")
    return output_file


if __name__ == "__main__":
    collect_all_database_schemas()
