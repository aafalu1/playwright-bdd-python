Feature: Checkout Flow with Nested Iframes
@regression
  Scenario: Pay inside nested iframe and verify order
    Given I navigate to the "Add to Cart" page
    When I fill the "Card Number" field with "4242424242424242"
    And I fill the "OTP" field with "123456"
    And I check the "Terms" checkbox
    And After I click the "Add to Cart" button it is disabled
    Then the "Order Row" label for "A-1001" should be visible