## Metadata

* **Smell name:** nested_forms
* **Expected smell location:** Function `calculate-total`
* **Affected forms:** `let`
* **Short explanation:** Combined nested let bindings into a single let block for better readability.

```Clojure
(ns shop.cart)

(defn calculate-total [cart]
  (let [items    (:items cart)
        subtotal (reduce + (map :price items))
        tax      (* subtotal 0.08)]
    (+ subtotal tax)))
```
