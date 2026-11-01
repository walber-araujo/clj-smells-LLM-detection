(ns orders
  (:require [clojure.java.io :as io]
            [clojure.core.async :as a]))

(defn read-orders-file [filename]
  (let [reader (io/reader filename)]
    (line-seq reader)))

(defn has-orders? [orders]
  (not (empty? orders)))

(defn discount-applies? [discount]
  (= discount 0))

(defn build-order-summary [order]
  (let [base {}
        base (if (:rush? order)
               (assoc base :priority :high)
               (assoc base :priority :normal))
        base (if (:vip? order)
               (assoc base :discount 0.1)
               (assoc base :discount 0))
        base (if (:paid? order)
               (assoc base :status :complete)
               (assoc base :status :pending))]
    base))

(defn order-ids [orders]
  (into [] (map :id orders)))

(defn build-order-map [id customer]
  {:id id
   :customer customer
   :shipped-at nil
   :cancelled-reason nil})

(defn log-order [order]
  (when (:paid? order)
    (do
      (println "Order paid:" (:id order))
      (println "Amount:" (:amount order)))))

(defn fetch-order-status [status-chan]
  (a/go
    (let [result (a/<!! status-chan)]
      (println "Status:" result))))

(def order-cache
  (atom {:by-id (atom {})
         :by-customer {}}))

(defrecord Order [id customer amount])

(defn make-order [id customer amount]
  (Order. id customer amount))
