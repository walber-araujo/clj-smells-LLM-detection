## Metadata

* **Smell name:** misuse_of_dynamic_scope
* **Expected smell location:** Top-level def `*shopping-cart*`
* **Affected forms:** `def ^:dynamic`, `binding`
* **Short explanation:** Using dynamic scope for ordinary application data like a shopping cart makes data flow implicit and harder to reason about.

```Clojure
(ns app.ecommerce.cart)

; VALIDATION: SMELL START - misuse_of_dynamic_scope
; VALIDATION: Using dynamic scope for ordinary application data (shopping cart)
(def ^:dynamic *shopping-cart* nil)
; VALIDATION: SMELL END

(defn calculate-total
  []
  (reduce + (map :price (:items *shopping-cart*))))

(defn process-cart
  [cart]
  (binding [*shopping-cart* cart]
    {:total (calculate-total)}))
```
