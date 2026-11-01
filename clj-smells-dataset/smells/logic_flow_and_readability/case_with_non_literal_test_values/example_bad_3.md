## Metadata

* **Smell name:** case_with_non_literal_test_values
* **Expected smell location:** Function `process-payment`
* **Affected forms:** `case`
* **Short explanation:** Uses function calls (which are treated as lists, not evaluated) as branch values in a case statement.

```Clojure
(ns payment.processor)

(defn get-stripe-id [] :stripe)
(defn get-paypal-id [] :paypal)

(defn process-payment [gateway amount]
  ; VALIDATION: SMELL START - case_with_non_literal_test_values
  ; VALIDATION: case uses function calls as branch test expressions; they won't be evaluated
  (case gateway
    (get-stripe-id) (pay-stripe amount)
    (get-paypal-id) (pay-paypal amount)
    (throw (ex-info "Unknown gateway" {}))))
  ; VALIDATION: SMELL END
```
