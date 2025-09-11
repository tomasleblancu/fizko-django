import React, { useState, useEffect, useMemo } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  ChevronUpIcon,
  ChevronDownIcon,
  EyeIcon,
  DownloadIcon,
  MoreVerticalIcon,
  SearchIcon,
  FilterIcon,
} from '@heroicons/react/24/outline';

// TypeScript interfaces based on Django API structure
interface DocumentType {
  code: number;
  name: string;
  category: string;
  is_dte: boolean;
}

interface Document {
  id: number;
  document_type: string;
  folio: string;
  issue_date: string;
  razon_social_receptor: string;
  rut_receptor: string;
  monto_total: number;
  monto_iva: number;
  monto_neto: number;
  tipo_operacion: 'venta' | 'compra';
  status: 'draft' | 'pending' | 'signed' | 'sent' | 'accepted' | 'rejected' | 'cancelled' | 'processed';
}

interface DocumentsResponse {
  results: Document[];
  count: number;
  next: string | null;
  previous: string | null;
  page: number;
  page_size: number;
}

interface DocumentStats {
  ventas: {
    total: number;
    cantidad: number;
    iva: number;
  };
  compras: {
    total: number;
    cantidad: number;
    iva: number;
  };
}

// Sort configuration type
type SortField = 'issue_date' | 'folio' | 'monto_total' | 'razon_social_receptor' | 'document_type';
type SortDirection = 'asc' | 'desc';

interface SortConfig {
  field: SortField;
  direction: SortDirection;
}

// Status badge configuration
const getStatusBadge = (status: Document['status']) => {
  const statusConfig = {
    draft: { label: 'Borrador', variant: 'secondary' as const },
    pending: { label: 'Pendiente', variant: 'outline' as const },
    signed: { label: 'Firmado', variant: 'default' as const },
    sent: { label: 'Enviado', variant: 'default' as const },
    accepted: { label: 'Aceptado', variant: 'success' as const },
    rejected: { label: 'Rechazado', variant: 'destructive' as const },
    cancelled: { label: 'Anulado', variant: 'secondary' as const },
    processed: { label: 'Procesado', variant: 'success' as const },
  };

  const config = statusConfig[status] || statusConfig.draft;
  return <Badge variant={config.variant}>{config.label}</Badge>;
};

// Format currency helper
const formatCurrency = (amount: number) => {
  return new Intl.NumberFormat('es-CL', {
    style: 'currency',
    currency: 'CLP',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
};

// Table loading skeleton component
const DocumentTableSkeleton = () => (
  <Table>
    <TableHeader>
      <TableRow>
        <TableHead>Tipo</TableHead>
        <TableHead>Folio</TableHead>
        <TableHead>Fecha</TableHead>
        <TableHead className="hidden md:table-cell">Emisor/Receptor</TableHead>
        <TableHead className="hidden lg:table-cell">RUT</TableHead>
        <TableHead>Monto</TableHead>
        <TableHead>Estado</TableHead>
        <TableHead className="w-10"></TableHead>
      </TableRow>
    </TableHeader>
    <TableBody>
      {Array.from({ length: 10 }).map((_, index) => (
        <TableRow key={index}>
          <TableCell><Skeleton className="h-4 w-12" /></TableCell>
          <TableCell><Skeleton className="h-4 w-16" /></TableCell>
          <TableCell><Skeleton className="h-4 w-20" /></TableCell>
          <TableCell className="hidden md:table-cell"><Skeleton className="h-4 w-32" /></TableCell>
          <TableCell className="hidden lg:table-cell"><Skeleton className="h-4 w-24" /></TableCell>
          <TableCell><Skeleton className="h-4 w-20" /></TableCell>
          <TableCell><Skeleton className="h-6 w-16 rounded-full" /></TableCell>
          <TableCell><Skeleton className="h-8 w-8 rounded" /></TableCell>
        </TableRow>
      ))}
    </TableBody>
  </Table>
);

interface DocumentsProps {
  companyId: number;
  onViewDocument?: (document: Document) => void;
  onDownloadDocument?: (document: Document) => void;
}

const Documents: React.FC<DocumentsProps> = ({
  companyId,
  onViewDocument,
  onDownloadDocument,
}) => {
  // State management
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<DocumentStats | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [typeFilter, setTypeFilter] = useState<'all' | 'venta' | 'compra'>('all');
  const [sortConfig, setSortConfig] = useState<SortConfig>({ field: 'issue_date', direction: 'desc' });
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [pageSize] = useState(50);

  // API calls
  const fetchDocuments = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        company_id: companyId.toString(),
        page: currentPage.toString(),
        page_size: pageSize.toString(),
      });

      if (typeFilter !== 'all') {
        params.append('tipo_operacion', typeFilter);
      }

      const response = await fetch(`/api/v1/documents/?${params}`);
      const data: DocumentsResponse = await response.json();

      setDocuments(data.results);
      setTotalCount(data.count);
      setTotalPages(Math.ceil(data.count / pageSize));
    } catch (error) {
      console.error('Error fetching documents:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const currentYear = new Date().getFullYear();
      const params = new URLSearchParams({
        company_id: companyId.toString(),
        start_date: `${currentYear}-01-01`,
        end_date: `${currentYear}-12-31`,
      });

      const response = await fetch(`/api/v1/documents/financial-summary/?${params}`);
      const data: DocumentStats = await response.json();
      setStats(data);
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, [companyId, currentPage, typeFilter]);

  useEffect(() => {
    fetchStats();
  }, [companyId]);

  // Filtering and sorting logic
  const filteredAndSortedDocuments = useMemo(() => {
    let filtered = documents.filter((doc) => {
      const matchesSearch = 
        doc.folio.toLowerCase().includes(searchTerm.toLowerCase()) ||
        doc.razon_social_receptor.toLowerCase().includes(searchTerm.toLowerCase()) ||
        doc.rut_receptor.toLowerCase().includes(searchTerm.toLowerCase());

      const matchesStatus = statusFilter === 'all' || doc.status === statusFilter;

      return matchesSearch && matchesStatus;
    });

    // Sort documents
    filtered.sort((a, b) => {
      const aValue = a[sortConfig.field];
      const bValue = b[sortConfig.field];

      if (sortConfig.field === 'issue_date') {
        const aDate = new Date(a.issue_date);
        const bDate = new Date(b.issue_date);
        return sortConfig.direction === 'asc' ? aDate.getTime() - bDate.getTime() : bDate.getTime() - aDate.getTime();
      }

      if (typeof aValue === 'number' && typeof bValue === 'number') {
        return sortConfig.direction === 'asc' ? aValue - bValue : bValue - aValue;
      }

      const aString = String(aValue).toLowerCase();
      const bString = String(bValue).toLowerCase();
      
      if (sortConfig.direction === 'asc') {
        return aString.localeCompare(bString);
      } else {
        return bString.localeCompare(aString);
      }
    });

    return filtered;
  }, [documents, searchTerm, statusFilter, sortConfig]);

  // Sort handler
  const handleSort = (field: SortField) => {
    setSortConfig((prevSort) => ({
      field,
      direction: prevSort.field === field && prevSort.direction === 'asc' ? 'desc' : 'asc',
    }));
  };

  // Sortable header component
  const SortableHeader: React.FC<{ field: SortField; children: React.ReactNode; className?: string }> = ({ 
    field, 
    children, 
    className = '' 
  }) => (
    <TableHead 
      className={`cursor-pointer hover:bg-muted/50 ${className}`}
      onClick={() => handleSort(field)}
    >
      <div className="flex items-center space-x-1">
        <span>{children}</span>
        {sortConfig.field === field && (
          sortConfig.direction === 'asc' ? 
            <ChevronUpIcon className="w-4 h-4" /> : 
            <ChevronDownIcon className="w-4 h-4" />
        )}
      </div>
    </TableHead>
  );

  // Handle document actions
  const handleViewDocument = (document: Document) => {
    onViewDocument?.(document);
  };

  const handleDownloadDocument = (document: Document) => {
    onDownloadDocument?.(document);
  };

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Ventas</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{formatCurrency(stats.ventas.total)}</div>
              <p className="text-xs text-muted-foreground">{stats.ventas.cantidad} documentos</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Compras</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{formatCurrency(stats.compras.total)}</div>
              <p className="text-xs text-muted-foreground">{stats.compras.cantidad} documentos</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">IVA Ventas</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{formatCurrency(stats.ventas.iva)}</div>
              <p className="text-xs text-muted-foreground">Impuestos generados</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">IVA Compras</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{formatCurrency(stats.compras.iva)}</div>
              <p className="text-xs text-muted-foreground">Crédito fiscal</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle>Documentos</CardTitle>
          <CardDescription>
            Gestiona y visualiza todos los documentos tributarios de la empresa
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col sm:flex-row gap-4 mb-6">
            {/* Search */}
            <div className="relative flex-1">
              <SearchIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground w-4 h-4" />
              <Input
                placeholder="Buscar por folio, receptor o RUT..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>

            {/* Type Filter */}
            <Select value={typeFilter} onValueChange={(value: typeof typeFilter) => setTypeFilter(value)}>
              <SelectTrigger className="w-full sm:w-40">
                <SelectValue placeholder="Tipo" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos</SelectItem>
                <SelectItem value="venta">Ventas</SelectItem>
                <SelectItem value="compra">Compras</SelectItem>
              </SelectContent>
            </Select>

            {/* Status Filter */}
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-full sm:w-40">
                <SelectValue placeholder="Estado" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos los estados</SelectItem>
                <SelectItem value="accepted">Aceptado</SelectItem>
                <SelectItem value="sent">Enviado</SelectItem>
                <SelectItem value="signed">Firmado</SelectItem>
                <SelectItem value="pending">Pendiente</SelectItem>
                <SelectItem value="rejected">Rechazado</SelectItem>
                <SelectItem value="cancelled">Anulado</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Documents Table */}
          <div className="border rounded-md">
            {loading ? (
              <DocumentTableSkeleton />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <SortableHeader field="document_type">Tipo</SortableHeader>
                    <SortableHeader field="folio">Folio</SortableHeader>
                    <SortableHeader field="issue_date">Fecha</SortableHeader>
                    <SortableHeader field="razon_social_receptor" className="hidden md:table-cell">
                      Emisor/Receptor
                    </SortableHeader>
                    <TableHead className="hidden lg:table-cell">RUT</TableHead>
                    <SortableHeader field="monto_total">Monto</SortableHeader>
                    <TableHead>Estado</TableHead>
                    <TableHead className="w-10">
                      <span className="sr-only">Acciones</span>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredAndSortedDocuments.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">
                        No se encontraron documentos
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredAndSortedDocuments.map((document) => (
                      <TableRow key={document.id} className="hover:bg-muted/50">
                        <TableCell>
                          <Badge variant="outline">{document.document_type}</Badge>
                        </TableCell>
                        <TableCell className="font-medium">{document.folio}</TableCell>
                        <TableCell>
                          {new Date(document.issue_date).toLocaleDateString('es-CL')}
                        </TableCell>
                        <TableCell className="hidden md:table-cell">
                          <div className="max-w-48 truncate">{document.razon_social_receptor}</div>
                        </TableCell>
                        <TableCell className="hidden lg:table-cell">
                          <div className="font-mono text-sm">{document.rut_receptor}</div>
                        </TableCell>
                        <TableCell>
                          <div className="font-medium">{formatCurrency(document.monto_total)}</div>
                        </TableCell>
                        <TableCell>
                          {getStatusBadge(document.status)}
                        </TableCell>
                        <TableCell>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="sm">
                                <MoreVerticalIcon className="w-4 h-4" />
                                <span className="sr-only">Acciones</span>
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem onClick={() => handleViewDocument(document)}>
                                <EyeIcon className="w-4 h-4 mr-2" />
                                Ver detalle
                              </DropdownMenuItem>
                              <DropdownMenuItem onClick={() => handleDownloadDocument(document)}>
                                <DownloadIcon className="w-4 h-4 mr-2" />
                                Descargar PDF
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            )}
          </div>

          {/* Pagination */}
          {!loading && totalPages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <div className="text-sm text-muted-foreground">
                Mostrando {((currentPage - 1) * pageSize) + 1} a {Math.min(currentPage * pageSize, totalCount)} de {totalCount} documentos
              </div>
              <div className="flex items-center space-x-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                  disabled={currentPage === 1}
                >
                  Anterior
                </Button>
                <div className="text-sm">
                  Página {currentPage} de {totalPages}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                  disabled={currentPage === totalPages}
                >
                  Siguiente
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default Documents;