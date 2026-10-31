"use client";

import { useRouter } from "next/navigation";
import { createColumnHelper, tableFeatures, useTable, type RowData } from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, TableSkeleton } from "@/components/states";
import { cn } from "@/lib/utils";

// Sorting and paging are done by the API (plan Section 10), so only the core row model is needed.
const features = tableFeatures({});

export function createColumns<T extends RowData>() {
  return createColumnHelper<typeof features, T>();
}

export interface SortState {
  key: string;
  order: "asc" | "desc";
}

type ColumnsOf<T extends RowData> = ReturnType<ReturnType<typeof createColumns<T>>["columns"]>;

export interface DataTableProps<T extends RowData> {
  data: T[];
  columns: ColumnsOf<T>;
  getRowId: (row: T) => string;
  /** Maps a column id to the API sort key. Columns not listed are not sortable. */
  sortKeys?: Record<string, string>;
  sort?: SortState;
  onSortChange?: (key: string) => void;
  rowHref?: (row: T) => string;
  loading?: boolean;
  refreshing?: boolean;
  error?: Error;
  onRetry?: () => void;
  empty?: { title: string; description?: string; action?: React.ReactNode };
  skeletonRows?: number;
  /** Column ids whose content is right-aligned (numbers). */
  rightAligned?: string[];
  rowClassName?: (row: T) => string | undefined;
  /** Narrowest width, in px, before the table scrolls sideways. Leave unset for compact tables. */
  minWidth?: number;
  label: string;
}

export function DataTable<T extends RowData>({
  data,
  columns,
  getRowId,
  sortKeys = {},
  sort,
  onSortChange,
  rowHref,
  loading,
  refreshing,
  error,
  onRetry,
  empty = { title: "Nothing to show" },
  skeletonRows = 8,
  rightAligned = [],
  rowClassName,
  minWidth,
  label,
}: DataTableProps<T>) {
  const router = useRouter();
  const table = useTable({ features, columns, data, getRowId });

  if (error) return <ErrorState message={error.message} onRetry={onRetry} />;
  if (loading) return <TableSkeleton rows={skeletonRows} columns={Math.min(columns.length, 7)} />;
  if (data.length === 0) return <EmptyState title={empty.title} description={empty.description} action={empty.action} />;

  return (
    <div className={cn("overflow-x-auto transition-opacity duration-150", refreshing && "opacity-70")}>
      <table aria-label={label} style={minWidth ? { minWidth } : undefined} className="w-full border-collapse text-left">
        <thead className="bg-surface">
          {table.getHeaderGroups().map((group) => (
            <tr key={group.id} className="border-b">
              {group.headers.map((header) => {
                const sortKey = sortKeys[header.column.id];
                const active = sort && sortKey === sort.key;
                const right = rightAligned.includes(header.column.id);
                return (
                  <th
                    key={header.id}
                    scope="col"
                    aria-sort={active ? (sort.order === "asc" ? "ascending" : "descending") : undefined}
                    className={cn("h-9 px-4 text-xs font-medium whitespace-nowrap text-muted-foreground", right && "text-right")}
                  >
                    {header.isPlaceholder ? null : sortKey && onSortChange ? (
                      <Button
                        variant="ghost"
                        size="xs"
                        className={cn("-mx-2 text-muted-foreground", active && "text-foreground", right && "flex-row-reverse")}
                        onClick={() => onSortChange(sortKey)}
                      >
                        <table.FlexRender header={header} />
                        {active ? (
                          sort.order === "asc" ? <ArrowUp aria-hidden /> : <ArrowDown aria-hidden />
                        ) : (
                          <ChevronsUpDown aria-hidden className="opacity-50" />
                        )}
                      </Button>
                    ) : (
                      <table.FlexRender header={header} />
                    )}
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => {
            const href = rowHref?.(row.original);
            return (
              <tr
                key={row.id}
                tabIndex={href ? 0 : undefined}
                onClick={href ? () => router.push(href) : undefined}
                onKeyDown={href ? (e) => e.key === "Enter" && router.push(href) : undefined}
                className={cn(
                  "h-11 border-b last:border-b-0 transition-colors duration-150",
                  href && "cursor-pointer hover:bg-brand-subtle focus-visible:bg-brand-subtle",
                  rowClassName?.(row.original),
                )}
              >
                {row.getAllCells().map((cell) => (
                  <td key={cell.id} className={cn("px-4 align-middle", rightAligned.includes(cell.column.id) && "text-right")}>
                    <table.FlexRender cell={cell} />
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}) {
  if (total === 0) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  const pages = Math.ceil(total / pageSize);
  return (
    <div className="flex h-12 items-center justify-between border-t px-4">
      <p className="tnum text-muted-foreground">
        {from}–{to} of {total} calls
      </p>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
          Previous
        </Button>
        <span className="tnum text-muted-foreground">
          Page {page} of {pages}
        </span>
        <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => onPageChange(page + 1)}>
          Next
        </Button>
      </div>
    </div>
  );
}
