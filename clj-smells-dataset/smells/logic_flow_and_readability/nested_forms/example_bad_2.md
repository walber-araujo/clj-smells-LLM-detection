## Metadata

* **Smell name:** nested_forms
* **Expected smell location:** Function `calculate-total`
* **Affected forms:** `let`
* **Short explanation:** Uses nested let bindings instead of combining them into a single let block.

```Clojure
(ns shop.cart)

(defn calculate-total [cart]
  ; VALIDATION: SMELL START - nested_forms
  ; VALIDATION: Nested let blocks instead of a single flattened let
  (let [items (:items cart)]
    (let [subtotal (reduce + (map :price items))]
      (let [tax (* subtotal 0.08)]
        (+ subtotal tax)))))
  ; VALIDATION: SMELL END
```
