import { ref, computed } from "vue"

export type ProductLine = "Athena2" | "X2"

interface ProductLineConfig {
  key: ProductLine
  label: string
  testTypes: string[]
  profiles: string[]
  agingTestType: string
}

const ATHENA2_CONFIG: ProductLineConfig = {
  key: "Athena2",
  label: "Athena2 产测",
  testTypes: ["se9_interface_test", "evb_interface_test"],
  profiles: ["SE9通用接口测试", "BM1688 EVB 通用接口测试", "SE9-16-BP1-18"],
  agingTestType: "se9_aging_test",
}

const X2_CONFIG: ProductLineConfig = {
  key: "X2",
  label: "SE13 产测",
  testTypes: ["se13_interface_test"],
  profiles: ["SE13通用接口测试"],
  agingTestType: "se13_aging_test",
}

const current = ref<ProductLine>(loadProductLine())

function loadProductLine(): ProductLine {
  try {
    const saved = localStorage.getItem("productLine")
    if (saved === "X2") return "X2"
  } catch {}
  return "Athena2"
}

function switchTo(line: ProductLine) {
  current.value = line
  try { localStorage.setItem("productLine", line) } catch {}
}

const config = computed<ProductLineConfig>(() =>
  current.value === "X2" ? X2_CONFIG : ATHENA2_CONFIG
)

const defaultTestType = computed(() => config.value.testTypes[0])

export function useProductLine() {
  return { current, config, defaultTestType, switchTo }
}
