// Define components that will be used by the generate_ui tool
// Updates the componentsMap object to map React components to the components defined in config/components-definition.ts

import React from 'react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table'
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from 'recharts'
import { ChartConfig, ChartContainer } from '@/components/ui/chart'
import { getComponent } from '@/lib/components-mapping'
import {
  addToCart,
  selectOrder,
  viewProductDetails
} from '@/config/user-actions'
import { Button } from '@/components/ui/button'
import { ShoppingCart, Info } from 'lucide-react'

const DEFAULT_IMAGE_URL =
  'https://www.legami.com/dw/image/v2/BDSQ_PRD/on/demandware.static/-/Sites-legami-master-catalog/default/dwf6da9456/images_legami/zoom/AG2616062_1.jpg?sw=1200&sh=1200'

const formatEUR = (value?: number) => {
  if (typeof value !== 'number' || isNaN(value)) return null
  try {
    return new Intl.NumberFormat('it-IT', {
      style: 'currency',
      currency: 'EUR',
      minimumFractionDigits: 2
    }).format(value)
  } catch {
    return `€ ${value.toFixed(2)}`
  }
}

const formatKey = (key: string) =>
  key.toLowerCase().replace(/[^a-zA-Z0-9]/g, '_')

const getChartConfig = (columns: { label: string; value: number }[]) => {
  const config: ChartConfig = {}

  columns.forEach((item: { label: string; value: number }) => {
    config[formatKey(item.label)] = {
      label: item.label,
      color: '#ffffff'
    }
  })

  return config
}

const getChartData = (columns: { label?: string; value?: string }[]) => {
  return columns
    .filter(item => !!item.label)
    .map((item: { label?: string; value?: string }, index: number) => {
      if (!item.label) {
        throw new Error('Label is required')
      }
      return {
        id: index,
        label: item.label,
        value: item.value !== undefined ? parseFloat(item.value) : 0,
        fill: '#000000'
      }
    })
}

export const HeaderComponent = ({ content }: { content?: string }) => {
  return (
    <div>
      <h1 className="text-sm text-stone-900 font-medium">{content}</h1>
    </div>
  )
}

export const BarChartComponent = ({
  columns
}: {
  columns?: { label?: string; value?: string }[]
}) => {
  if (!columns) return null
  const chartData = getChartData(columns)
  const chartConfig = getChartConfig(chartData)
  return (
    <ChartContainer config={chartConfig} className="">
      <BarChart accessibilityLayer data={chartData}>
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey="label"
          tickLine={false}
          tickMargin={10}
          axisLine={false}
          padding={{ left: 10, right: 10 }}
        />
        <YAxis orientation="left" width={24} />
        <Bar dataKey="value" fill="#1A535C" radius={6} barSize={30} />
      </BarChart>
    </ChartContainer>
  )
}

export const TableComponent = ({
  columns,
  rows
}: {
  columns?: { key?: string; title?: string }[]
  rows?: any[]
}) => (
  <Table>
    <TableHeader>
      <TableRow>
        {columns?.map((column, index) => (
          <TableHead key={index}>{column.title}</TableHead>
        ))}
      </TableRow>
    </TableHeader>
    <TableBody>
      {rows?.map((row, index) => (
        <TableRow key={index}>
          {row.values?.map((value: string, index: number) => (
            <TableCell key={index}>{value}</TableCell>
          ))}
        </TableRow>
      ))}
    </TableBody>
  </Table>
)

export const ItemComponent = ({
  id,
  item_name,
  primary_image,
  description,
  price,
  match
}: any) => (
  <div className="flex flex-col mb-3 gap-3 justify-between border border-stone-200 bg-white p-4 rounded-xl shadow-sm hover:shadow-md transition-all hover:-translate-y-0.5 flex-shrink-0 w-full h-[500px] overflow-hidden">
    <div className="flex items-center gap-2 text-xs font-semibold tracking-wide text-white">
      <span className="bg-[#e30613] px-2 py-0.5 rounded">LEGAMI</span>
    </div>
    <div className="flex flex-col">
      <div className="rounded-lg overflow-hidden text-center h-44 bg-stone-100 flex items-center justify-center">
        <img
          src={
            primary_image && primary_image.match(/\.(jpeg|jpg|gif|png|webp)$/)
              ? `/imgs/${primary_image}`
              : DEFAULT_IMAGE_URL
          }
          alt={item_name || 'Product Image'}
          className="w-full h-full object-cover object-center"
        />
      </div>
      <div className="flex flex-col gap-1 justify-start mt-2">
        <h3 className="text-sm font-semibold text-stone-800 line-clamp-2">
          {item_name ?? ''}
        </h3>
        <p className="text-xs text-stone-500 line-clamp-5">
          {description ?? ''}
        </p>
      </div>
    </div>
    <div className="mt-auto">
      {typeof price === 'number' && !isNaN(price) ? (
        <div className="flex items-baseline gap-2">
          <span className="font-semibold text-stone-900 text-lg">
            {formatEUR(price)}
          </span>
        </div>
      ) : null}
      {typeof match === 'number' && match >= 0 ? (
        <div className="mt-1 text-xs font-medium text-emerald-600">
          {Math.round(Math.max(0, Math.min(1, match)) * 100)}% match
        </div>
      ) : null}
      <div className="mt-2 grid grid-cols-2 gap-2 relative z-[60]">
        <Button
          size="sm"
          variant="secondary"
          className="rounded-full h-8 px-3 bg-stone-100 hover:bg-stone-200 text-stone-700 border border-stone-300 gap-1 w-full"
          onClick={() => viewProductDetails(id)}
        >
          <Info className="h-4 w-4" />
          Dettagli
        </Button>
        <Button
          size="sm"
          className="rounded-full h-8 px-3 bg-[#e30613] hover:bg-[#c20510] text-white whitespace-nowrap gap-1 w-full"
          onClick={() => addToCart(id)}
        >
          <ShoppingCart className="h-4 w-4" />
          Aggiungi
        </Button>
      </div>
    </div>
  </div>
)

// Simple PLP-style grid wrapper (3 columns by default)
export const PlpGridComponent = ({
  children,
  columns
}: {
  children?: any[]
  columns?: number
}) => {
  const cols = columns && columns >= 1 ? Math.min(columns, 6) : 3
  // Tailwind requires explicit classes; map allowed options
  const gridColsClass =
    cols === 2
      ? 'md:grid-cols-2'
      : cols === 4
      ? 'md:grid-cols-4'
      : cols === 5
      ? 'md:grid-cols-5'
      : cols === 6
      ? 'md:grid-cols-6'
      : 'md:grid-cols-3'
  const sorted = (children || []).slice().sort((a: any, b: any) => {
    const ma = typeof a?.match === 'number' ? a.match : 0
    const mb = typeof b?.match === 'number' ? b.match : 0
    return mb - ma // relevance desc
  })
  return (
    <div className={`grid grid-cols-1 ${gridColsClass} gap-4 w-full`}>
      {sorted.map((child: any, index: number) => (
        <React.Fragment key={index}>{getComponent(child)}</React.Fragment>
      ))}
    </div>
  )
}

export const OrderComponent = ({ id, total, date, status, products }: any) => (
  <div className="flex flex-col gap-2 mb-3">
    <div className="flex flex-col justify-between rounded-lg border bg-white p-4 w-96 h-72 flex-shrink-0">
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between text-gray-800">
          <div className="flex items-center gap-2">
            Order <span className="font-semibold"> #{id ?? ''} </span>
          </div>
          <div className="text-xs border border-gray-500 rounded-md px-1.5 py-0.5 text-gray-500">
            {status ?? ''}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="text-xs text-gray-500">{date ?? ''}</div>
        </div>
        <div className="flex flex-col gap-2 mt-2">
          {products?.map((product: any, index: number) => (
            <div className="flex items-center gap-2" key={index}>
              <div className="aspect-h-1 aspect-w-1 w-16 h-16 overflow-hidden rounded-lg bg-gray-100 border border-gray-200 xl:aspect-h-8 xl:aspect-w-7">
                {product.item?.primary_image &&
                product.item.primary_image.match(
                  /\.(jpeg|jpg|gif|png|webp)$/
                ) ? (
                  <img
                    src={`/imgs/${product.item.primary_image}`}
                    alt={product.item.item_name}
                    className="h-full w-full object-cover object-center"
                  />
                ) : (
                  <div className="animate-pulse bg-gray-200 h-full w-full"></div>
                )}
              </div>

              <div className="text-xs text-gray-600 flex-1 text-ellipsis text-nowrap overflow-hidden">
                <span className="text-ellipsis">
                  {product.item?.item_name ?? ''}
                </span>
                <span className="font-semibold ml-1">
                  x {product.quantity ?? ''}
                </span>
              </div>
              <div className="text-xs font-semibold text-gray-800">
                {formatEUR(product.item?.price)}
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="flex items-center justify-between">
        <div className="text-gray-500 font-semibold">Total</div>
        <div className="font-medium text-gray-900 ">{formatEUR(total)}</div>
      </div>
    </div>
    <div className="flex justify-start">
      <Button size="sm" onClick={() => selectOrder(id)}>
        Select order
      </Button>
    </div>
  </div>
)

export const CardComponent = ({ children }: { children?: any[] }) => (
  <div className="flex flex-col w-full bg-white rounded-lg p-4 shadow-md mt-2">
    {children ? (
      <div className="flex flex-col gap-4">
        {children.map((child: any, index: number) => (
          <React.Fragment key={index}>{getComponent(child)}</React.Fragment>
        ))}
      </div>
    ) : null}
  </div>
)

export const CarouselComponent = ({ children }: { children?: any[] }) => (
  <div className="flex space-x-2 overflow-x-scroll w-full">
    {children
      ? children.map((child: any, index: number) => (
          <React.Fragment key={index}>{getComponent(child)}</React.Fragment>
        ))
      : null}
  </div>
)

export const componentsMap = {
  card: CardComponent,
  carousel: CarouselComponent,
  plp_grid: PlpGridComponent,
  bar_chart: BarChartComponent,
  header: HeaderComponent,
  table: TableComponent,
  item: ItemComponent,
  order: OrderComponent
  // update componentsMap to match components passed to generate_ui
}
